import torch

# def find_parents(N):
#     parent_list = []
#     current_parent = (N-1)//2
#     while(current_parent is not 0):
#         parent_list.append(current_parent)
#         current_parent = (current_parent-1)//2
#     return parent_list

# print(find_parents(16))

# ml = [1,2,4,4,5,5,6,7,7,3,3]
# ml2 = list(set(ml))
# print(ml2)

# def find_leaves(node_list):
#     leaf_list = []
#     for node in node_list:
#         #check if no left-node children:
#         if (not (node_list == 2*node+1).sum().item()) & (not (node_list == 2*node+2).sum().item()):
#             if (node%2).item():
#                 if (node_list == node+1).sum().item():
#                     leaf_list.append(node)
#                 else:
#                     leaf_list.append((node-1)//2)
#             else: 
#                 if (node_list == node-1).sum().item():
#                     leaf_list.append(node)
#                 else:
#                     leaf_list.append((node-1)//2)
#     return torch.unique(torch.FloatTensor(leaf_list))

# a = torch.FloatTensor([0,1,2,3,4,5,6])
# for i in range(len(a)+1):
#     b=find_leaves(a[:i])
#     print(b)

def some_func(a=None):
    if(a):
        print('press play')
    else:
        print('go away')

some_func()