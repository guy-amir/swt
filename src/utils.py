"""
some utiliy functions.
"""
import matplotlib.pyplot as plt
from matplotlib.patches import ConnectionPatch
import numpy as np
import torch

cifar10_class_name = ['airplane', 'automobile', 'bird', 'cat', 'deer', 'dog', 
                      'frog', 'horse', 'ship', 'truck']

def show_data(dataset, name):
    """
    show some image from the dataset.
    args:
        dataset: dataset to show
        name: name of the dataset
    """
    if name == 'mnist':
        num_test = len(dataset)
        num_shown = 100
        cols = 10
        rows = int(num_shown/cols)
        indices = np.random.choice(list(range(num_test)), num_test)
        plt.figure()
        for i in range(num_shown):
            plt.subplot(rows, cols, i+1)
            plt.imshow(dataset[indices[i]][0].squeeze().numpy())
            plt.axis('off')
            plt.title(str(dataset[indices[i]][1].data.item()))
        plt.gcf().tight_layout()
        plt.show()
    else:
        raise NotImplementedError
    return

def get_sample(dataset, sample_num, name):
    # random seed
    #np.random.seed(2019)
    """
    get a batch of random sample images from the dataset
    args:
        dataset: dataset to use
        sample_num: number of samples
        name: name of the dataset
    return:
        selected sample
    """
    indices = np.random.choice(list(range(len(dataset))), sample_num)
    if name in ['mnist', 'cifar10']:
        # for MNIST and CIFAR-10 dataset
        sample = [dataset[indices[i]][0].unsqueeze(0) for i in range(len(indices))]
        sample = torch.cat(sample, dim = 0)
    else:
        raise ValueError     
    return sample

def revert_preprocessing(data_tensor, name):
    """
    unnormalize the data tensor
    args:
        data_tensor: input data tensor
        name
    return:
        data_tensor: processed data tensor
    """
    if name == 'mnist':
        data_tensor = data_tensor*0.3081 + 0.1307
    elif name == 'cifar10':
        data_tensor[:,0,:,:] = data_tensor[:,0,:,:]*0.2023 + 0.4914     
        data_tensor[:,1,:,:] = data_tensor[:,1,:,:]*0.1994 + 0.4822      
        data_tensor[:,2,:,:] = data_tensor[:,2,:,:]*0.2010 + 0.4465      
    else:
        raise NotImplementedError
    return data_tensor

def normalize(gradient, name):
    """
    normalize the gradient for display
    args:
        gradient: input gradent tensor
        name: name of the dataset
    return:
        gradient: normalized gradient tensor
    """
    if name == 'mnist':
        pass
    elif name == 'cifar10':
        # take the maximum gradient from the 3 channels
        gradient = (gradient.max(dim=1)[0]).unsqueeze(dim=1)
    # get the maximum gradient
    max_gradient = torch.max(gradient.view(len(gradient), -1), dim=1)[0]
    max_gradient = max_gradient.view(len(gradient), 1, 1, 1)
    min_gradient = torch.min(gradient.view(len(gradient), -1), dim=1)[0]
    min_gradient = min_gradient.view(len(gradient), 1, 1, 1)    
    # do normalization
    gradient = (gradient - min_gradient)/(max_gradient - min_gradient)    
    return gradient

def trace(record):
    """
    get the most likely splitting nodes to visit and probabilities 
    for one input sample
    args:
        record: record of the routing probabilities of the splitting nodes
    return:
        path: the most likely path
    """
    path = []
    # probability of arriving at the root node
    prob = 1
    # the starting index 
    node_idx = 1
    while node_idx < len(record):
        path.append((node_idx, prob))
        # find the children node with larger visiting probability
        if record[node_idx] >= 0.5:
            prob *= record[node_idx]
            node_idx = node_idx*2
        else:
            prob *= 1 - record[node_idx]
            node_idx = node_idx*2 + 1          
    return path

def get_paths(dataset, model, tree_idx, name):
    """
    compute the computational paths for the input tensors
    """
    sample_num = 5
    sample = get_sample(dataset, sample_num, name)   
    # forward pass
    pred, cache, _ = model(sample.cuda(), save_flag = True)
    class_pred = pred.max(dim=1)[1]
    decision = cache[0]['decision'].data.cpu().numpy()
    paths = []
    for sample_idx in range(len(decision)):
        paths.append(trace(decision[sample_idx, :]))
    return sample, paths, class_pred

def get_node_saliency_map(dataset, model, tree_idx, node_idx, name):
    # pick some samples from the dataset
    sample_num = 5
    sample = get_sample(dataset, sample_num, name)
    # enable the gradient computation
    sample = sample.cuda()
    sample.requires_grad = True
    # for NDF architecture
    feats = model.feature_layer(sample)
    # note that the first using_idx is not used for ndf
    using_idx = model.forest.trees[tree_idx].using_idx[node_idx + 1]
#    for sample_idx in range(len(feats)):
#        feats[sample_idx, using_idx].backward(retain_graph=True)
    # should be equivalent to the above one
    feats[:, using_idx].sum(dim = 0).backward()
    # get the gradient
    gradient = sample.grad.data
    # compute the magnitude
    gradient = torch.abs(gradient)
    gradient = normalize(gradient, name)
    # plot the input data and their corresponding saliency maps
    plt.figure()
    # revert pre-processing operations
    sample = revert_preprocessing(sample, name)
    for sample_idx in range(sample_num):
        plt.subplot(2, sample_num, sample_idx + 1)
        sample_to_show = sample[sample_idx].squeeze().data.cpu().numpy()
        if name == 'cifar10':
            # re-order the channels
            sample_to_show = sample_to_show.transpose((1,2,0))
            plt.imshow(sample_to_show)
        elif name == 'mnist':
            plt.imshow(sample_to_show, cmap='gray')
        else:
            raise NotImplementedError
        plt.subplot(2, sample_num, sample_idx + 1 + sample_num)
        plt.imshow(gradient[sample_idx].squeeze().cpu().numpy())
    plt.axis('off')
    plt.show()
    return gradient

def get_map(model, sample, node_idx, tree_idx, name):
    # helper function for computing the saliency map for a specified sample
    # and node
    sample = sample.unsqueeze(dim=0).cuda()
    sample.requires_grad = True
    feat = model.feature_layer(sample)
    using_idx = model.forest.trees[tree_idx].using_idx[node_idx]
    feat[:, using_idx].backward()
    gradient = sample.grad.data
    gradient = normalize(torch.abs(gradient), name)
    saliency_map = gradient.squeeze().cpu().numpy()
    return saliency_map

def get_path_saliency(samples, paths, class_pred, model, tree_idx, name, orientation = 'horizontal'):
    # show the saliency maps for the input samples with their 
    # computational paths 
    #plt.ioff()
    plt.figure(figsize=(20,5))
    plt.rcParams.update({'font.size': 12})
    num_samples = len(samples)
    path_length = len(paths[0])
    for sample_idx in range(num_samples):
        sample = samples[sample_idx]
        # plot the sample
        plt.subplot(num_samples, path_length + 1, sample_idx*(path_length + 1) + 1)
        sample_to_plot = revert_preprocessing(sample.unsqueeze(dim=0), name)
        if name == 'mnist':
            plt.imshow(sample_to_plot.squeeze().cpu().numpy(), cmap='gray')
            pred_class_name = str(int(class_pred[sample_idx]))
        else:
            plt.imshow(sample_to_plot.squeeze().cpu().numpy().transpose((1,2,0)))            
            pred_class_name = cifar10_class_name[int(class_pred[sample_idx])]
        plt.axis('off')        
        plt.title('Pred:{:s}'.format(pred_class_name))
        path = paths[sample_idx]
        for node_idx in range(path_length):
            # compute and plot saliency for each node
            node = path[node_idx][0]
            # probability of arriving at this node
            prob = path[node_idx][1]            
            saliency_map = get_map(model, sample, node, tree_idx, name)
            if orientation == 'horizontal':
                sub_plot_idx = sample_idx*(path_length + 1) + node_idx + 2
                plt.subplot(num_samples, path_length + 1, sub_plot_idx)
            elif orientation == 'vertical':
                raise NotImplementedError             
            else:
                raise NotImplementedError
            plt.imshow(saliency_map)
            #axe.set_title('(N{:d}, P{:.2f})'.format(node, prob), font_size=8)
            plt.title('(N{:d}, P{:.2f})'.format(node, prob))
            plt.axis('off')
        # draw some arrows 
        for arrow_idx in range(num_samples*(path_length + 1) - 1):
            if (arrow_idx+1) % (path_length+1) == 0 and arrow_idx != 0:
                continue
            ax1 = plt.subplot(num_samples, path_length + 1, arrow_idx + 1)
            ax2 = plt.subplot(num_samples, path_length + 1, arrow_idx + 2)
            arrow = ConnectionPatch(xyA=[1.1,0.5], xyB=[-0.1, 0.5], coordsA='axes fraction', coordsB='axes fraction',
                      axesA=ax1, axesB=ax2, arrowstyle="fancy")
            ax1.add_artist(arrow)
    left  = 0  # the left side of the subplots of the figure
    right = 1    # the right side of the subplots of the figure
    bottom = 0.01   # the bottom of the subplots of the figure
    top = 0.95      # the top of the subplots of the figure
    wspace = 0.0 # the amount of width reserved for space between subplots,
                   # expressed as a fraction of the average axis width
    hspace = 0.4   # the amount of height reserved for space between subplots,
                   # expressed as a fraction of the average axis height  
    plt.subplots_adjust(left, bottom, right, top, wspace, hspace)
    plt.show()
    #plt.savefig('saved_fig.png',dpi=1200)
    return