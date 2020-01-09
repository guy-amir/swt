import torch
import torch.nn.functional as F
import numpy as np
import os
import logging
from wavelets import wavelet
import wavelets as w
import matplotlib.pyplot as plt
import pandas
# minimum float number
FLT_MIN = float(np.finfo(np.float32).eps)


def prepare_batches(model, dataset, num_of_batches, opt):
    """
    prepare some feature vectors for leaf node update.
    args:
        model: the neural decison forest to be trained
        dataset: the used dataset
        num_of_batches: total number of batches to prepare
        opt: experiment configuration object
    return: target vectors used for leaf node update
    """
    cls_onehot = torch.eye(opt.n_class)
    target_batches = []
    with torch.no_grad():
        # the features are prepared from the feature layer
        train_loader = torch.utils.data.DataLoader(dataset, 
                                                   batch_size = opt.batch_size, 
                                                   shuffle = True)
       
        for batch_idx, (data, target) in enumerate(train_loader):
            if batch_idx == num_of_batches:
                # enough batches
                break
            if opt.cuda:
                # move tensors to GPU if needed
                data, target, cls_onehot = data.cuda(), target.cuda(), \
                cls_onehot.cuda()
            # get the feature vectors
            feats = model.feature_layer(data)
            # release some memory
            del data
            feats = feats.view(feats.size()[0],-1)
            for tree in model.forest.trees:  
                # compute routing probability for each tree and cache them
                mu = tree(feats)
                mu += FLT_MIN
                tree.mu_cache.append(mu)  
            del feats
            target_batches.append(cls_onehot[target])    
    return target_batches

def evaluate(model, dataset, opt):
    """
    evaluate the neural decison forest.
    args:
        dataset: the evaluation dataset
        opt: experiment configuration object
    return: 
        record: evaluation statistics
    """
    # set the model in evaluation mode
    model.eval()
    # average evaluation loss
    test_loss = 0
    # total correct predictions
    correct = 0      
    test_loader = torch.utils.data.DataLoader(dataset, 
                                              batch_size = opt.batch_size, 
                                              shuffle = False)
    for data, target in test_loader:
        with torch.no_grad():
            if opt.cuda:
                data, target = data.cuda(), target.cuda()
            # get the output vector
            output = model(data, save_flag=True) ##GG added save_flag=True
            
            #GGGG
            feats = model.feature_layer(data)
            feats = feats.view(feats.size()[0],-1)
            for tree in model.forest.trees:  
                # compute routing probability for each tree and cache them
                mu = tree(feats)
                mu += FLT_MIN
                # tree.nu_cache.append(mu)  GG
            del feats
            del mu
            #GG big_cache = nu_to_big(tree.nu_cache)
            # mean_cache = torch.stack(model.forest.trees[0].nu_cache[:-1]).mean(0)
            #GG big_cache = bigger_cache(big_cache)
            
            # loss function                
            test_loss += F.nll_loss(torch.log(output[0]), target, reduction='sum').data.item() # sum up batch loss ##GG turned output to output[0] to avoid tuple error
            # get class prediction
            ##GG old: pred = output.data.max(1, keepdim = True)[1] # get the index of the max log-probability
            ##GG mod:
            pred = output[0].max(1, keepdim = True)[1]
            # count correct prediction
            correct += pred.eq(target.data.view_as(pred)).cpu().sum()
    # averaging
    test_loss /= len(test_loader.dataset)
    test_acc = int(correct) / len(dataset)
    record = {'loss':test_loss, 'acc':test_acc, 'corr':correct}
    return record

def wavaluate(model, dataset, opt): #like evaluate only with wavelets - get it?!
    """
    evaluate the neural decison forest.
    args:
        dataset: the evaluation dataset
        opt: experiment configuration object
    return: 
        record: evaluation statistics
    """
    cutoff_record = []
    J = []
    LOSS = []
    mu_list = []
    target_list = []
    # set the model in evaluation mode
    model.eval()
    # average evaluation loss
    test_loss = 0
    # total correct predictions
    correct = 0      
    test_loader = torch.utils.data.DataLoader(dataset, 
                                              batch_size = opt.batch_size, 
                                              shuffle = False)

    for data, target in test_loader:
        target_list.append(target)
        with torch.no_grad():
            if opt.cuda:
                
                data, target = data.cuda(), target.cuda()
            # get the output vector
            output = model(data, save_flag=True) ##GG added save_flag=True
            
            #GGGG
            feats = model.feature_layer(data)
            feats = feats.view(feats.size()[0],-1)
            for tree in model.forest.trees:  
                # compute routing probability for each tree and cache them
                mu = tree(feats)
                mu += FLT_MIN
                mu_list.append(mu) 
                del mu
            del feats
            
    MU = torch.cat(mu_list,0)
    TARGET = torch.cat(target_list,0).cuda()
    for i in range(1,15):#range(2*(2**(opt.tree_depth))-1):
        j=5*i
        ww = w.wavelet(tree)
        leaf_list = ww.cutoff(j)
        nu  = w.mod_mu(MU,leaf_list)
        pu  = w.mod_pi(tree.pi,leaf_list)
        p = tree.cal_prob(nu, pu)
        
        #GG big_cache = nu_to_big(tree.nu_cache)
        # mean_cache = torch.stack(model.forest.trees[0].nu_cache[:-1]).mean(0)
        #GG big_cache = bigger_cache(big_cache)
        

        # loss function                
        test_loss += F.nll_loss(torch.log(p), TARGET, reduction='sum').data.item() # sum up batch loss ##GG turned output to output[0] to avoid tuple error
        # get class prediction
        ##GG old: pred = output.data.max(1, keepdim = True)[1] # get the index of the max log-probability
        ##GG mod:
        pred = p.max(1, keepdim = True)[1]
        # count correct prediction
        correct += pred.eq(TARGET.data.view_as(pred)).cpu().sum()
        # averaging
        test_loss /= len(test_loader.dataset)
        test_acc = int(correct) / len(dataset)
        record = {'loss':test_loss, 'acc':test_acc, 'corr':correct, 'cutoff':j}
        cutoff_record.append(record)
        J.append(j)
        LOSS.append(test_loss)
    return [J,LOSS]

def train(model, optim, sche, db, opt):


    """
    model training function.
    args:
        model: the neural decison forest to be trained
        optim: the optimizer
        sche: learning rate scheduler
        db: dataset object
        opt: experiment configuration object
    return:
        best_eval_acc: best evaluation accuracy
    """    
    # some initialization
    iteration_num = 0
    # number of batches to use for leaf node update
    num_of_batches = int(opt.label_batch_size/opt.batch_size)
    # number of images
    num_train = len(db['train'])
    num_test = len(db['eval'])
    # best evaluation accuracy
    best_eval_acc = 0
    # start training
    for epoch in range(1, opt.epochs + 1):
        # update learning rate by the scheduler
        sche.step()
    
        # Update leaf node prediction vector
        logging.info("Epoch %d : update leaf node distribution"%(epoch))

        # prepare feature vectors for leaf node update        
        target_batches = prepare_batches(model, db['train'],
                                         num_of_batches, opt)
        
        # update leaf node prediction vectors for every tree         
        for tree in model.forest.trees:
            for _ in range(20):
                tree.update_label_distribution(target_batches)
            # clear the cache for routing probabilities
            # tree.construct_wavelet()
            tree.nu = tree.mu_cache
            del tree.mu_cache
            tree.mu_cache = []
            
        # optimize decision functions
        model.train()
        train_loader = torch.utils.data.DataLoader(db['train'],
                                                   batch_size=opt.batch_size, 
                                                   shuffle=True)
        for batch_idx, (data, target) in enumerate(train_loader):
            if opt.cuda:
                # move tensors to GPU
                with torch.no_grad():
                    data, target = data.cuda(), target.cuda()
            iteration_num += 1
            optim.zero_grad()
            output = model(data, save_flag=True)
            output = output[0].clamp(min=1e-6, max=1) # resolve some numerical issue ##GG output -> output[0]
            # loss function
            loss = F.nll_loss(torch.log(output), target)              
            # compute gradients
            loss.backward()
            # update network parameters
            optim.step()
            
            # logging
            if batch_idx % opt.report_every == 0:
                logging.info('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(\
                    epoch, batch_idx * len(data), num_train,\
                    100. * batch_idx / len(train_loader), loss.data.item()))    
        
                        
        # Evaluate after every epoch
        eval_record = evaluate(model, db['eval'], opt)
        if eval_record['acc'] > best_eval_acc:
            best_eval_acc = eval_record['acc']

            ##GG for wavelets:
            # if opt.wavelets:
                # for tree in model.forest.trees:
                    #currently works for 1 tree in forest - FIX me
                    # wavelet_nu = tree.nu
                    # wavelet_pi = tree.pi
            ##GG END for wavelets

            # save a snapshot of model when hitting a higher accuracy
            if opt.save and epoch > opt.epochs/2:
                save_path = os.path.join(opt.save_dir,
                           'depth_' + str(opt.tree_depth) +
                           'n_tree' + str(opt.n_tree) + \
                           'archi_type_' + opt.model_type + '_' + str(best_eval_acc) + \
                           '.pth')
                if not os.path.exists(opt.save_dir):
                    os.makedirs(opt.save_dir)
                torch.save(model, save_path)       
        # logging 
        logging.info('\nTest set: Average loss: {:.4f}, Accuracy: {}/{} ({:.4f})\n'.format(
            eval_record['loss'], eval_record['corr'], num_test, eval_record['acc']))
    if opt.wavelets:
        wt = [] #GG wavelet order tracker
        w = wavelet(tree)
        wt.append(w.psi.Norm_order)  #GG add to wavelet order tracker
        # print(f'norm order:{wt}')   
        [J,LOSS] = wavaluate(model, db['eval'], opt)
        plt.plot(J,LOSS)
        plt.show()
    print('.')
    return best_eval_acc