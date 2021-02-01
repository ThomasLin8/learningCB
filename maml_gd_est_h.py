# -*- coding: utf-8 -*-
"""
Created on Tue Jan 12 12:13:53 2021

@author: ethan
"""

import sys
sys.path.append('D:\\Github Repositories\\learn2learn')
import numpy as np
import matplotlib.pyplot as plt
from ComplexLayers_Torch import PhaseShifter, PowerPooling, ComputePower
import torch.utils.data
import torch.optim as optim
import torch.nn as nn
from sklearn.model_selection import train_test_split
from beam_utils import DFT_codebook, GaussianCenters

import random
import torch
from learn2learn.algorithms import MAML
from learn2learn.utils import clone_module,detach_module

seed = 7
np.random.seed(seed)
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)

# num_of_beams = [2, 4, 8, 16, 32, 64, 96, 128]
num_of_beams = [8,16,24,32,64,128]
num_antenna = 64
antenna_sel = np.arange(num_antenna)

# --------------------------
# MAML training parameters
# --------------------------
batch_size = 10
nepoch = 1000
shots = 50
update_step = 1
ntest = 50
nval = 10
h_est_force_z = True #

fast_lr = 0.5
meta_lr = 0.5

# --------------------------
# UE distribution generator parameters (clusters)
# --------------------------
n_clusters = 10
arrival_rate = int(shots*2/n_clusters)
cluster_variance = 10

plot_training_loss_history = False
#-------------------------------------------#
# Load channel data and UE locations
# Scale channel data by max 1-norm
# Compute EGC gain
#-------------------------------------------#
h_real = np.load('D://Github Repositories/mmWave Beam Management/H_Matrices FineGrid/MISO_Static_FineGrid_Hmatrices_real.npy')[:,antenna_sel]
h_imag = np.load('D://Github Repositories/mmWave Beam Management/H_Matrices FineGrid/MISO_Static_FineGrid_Hmatrices_imag.npy')[:,antenna_sel]
loc = np.load('D://Github Repositories/mmWave Beam Management/H_Matrices FineGrid/MISO_Static_FineGrid_UE_location.npy')

BS_loc = [641,435,10]
num_samples = h_real.shape[0]
h = h_real + 1j*h_imag
#norm_factor = np.max(np.power(abs(h),2))
norm_factor = np.max(abs(h))
h_scaled = h/norm_factor
h_concat_scaled = np.concatenate((h_real/norm_factor,h_imag/norm_factor),axis=1)
# Compute EGC gain
egc_gain_scaled = np.power(np.sum(abs(h_scaled),axis=1),2)/num_antenna


class AnalogBeamformer(nn.Module):
    def __init__(self, n_antenna = 64, n_beam = 64, theta = None):
        super(AnalogBeamformer, self).__init__()
        self.codebook = PhaseShifter(in_features=2*n_antenna, out_features=n_beam, scale=np.sqrt(n_antenna), theta = theta)
        self.beam_selection = PowerPooling(2*n_beam)
        self.compute_power = ComputePower(2*n_beam)
    def forward(self, x, z) -> None:
        bf_signal = self.codebook(x)
        # bf_power_sel = self.beam_selection(bf_signal)
        # return bf_power_sel
        if not z is None:
            diff = z - bf_signal.detach().clone()
            bf_signal = bf_signal + diff
            bf_power = self.compute_power(bf_signal)
            bf_power_sel = torch.max(bf_power, dim=-1)[0]
            bf_power_sel = torch.unsqueeze(bf_power_sel,dim=-1)
        else:
            bf_power_sel = self.beam_selection(bf_signal)
        return bf_power_sel
    
    def get_theta(self) -> torch.Tensor:
        return self.codebook.get_theta()
    def get_weights(self) -> torch.Tensor:
        return self.codebook.get_weights()

def bf_gain_loss(y_pred, y_true):
    return -torch.mean(y_pred,dim=0)

def estimate_h(h_batch, model, n_antenna, h_est_force_z = False):
    # h_batch_complex = h_batch[:,:n_antenna] + 1j*h_batch[:,n_antenna:]
    # # theta = model.codebook.theta.detach().clone().numpy()
    # # bf_codebook = np.exp(1j*theta)/np.sqrt(n_antenna)
    # bf_codebook = DFT_codebook(n_antenna, n_antenna).T
    # z = bf_codebook.conj().T @ h_batch_complex.T
    # h_est = np.linalg.pinv(bf_codebook.conj().T) @ z
    # h_est_cat = np.concatenate((h_est.real, h_est.imag),axis=0)
    
    bf_weights = model.get_weights().numpy()
    z = h_batch @ bf_weights
    h_est_cat = np.linalg.pinv(bf_weights.T) @ z.T
    z_var = None
    if h_est_force_z:
        z_var = z
    return h_est_cat.T, z_var

def fit_genius(model:AnalogBeamformer, train_loader, val_loader, opt, loss_fn, EPOCHS):
    optimizer = opt
    train_loss_hist = []
    val_loss_hist = []
    for epoch in range(EPOCHS):
        model.train()
        train_loss = 0
        for batch_idx, (X_batch, y_batch) in enumerate(train_loader):
            theta = model.codebook.theta.detach().clone().numpy()
            learned_codebook = np.exp(1j*theta)/np.sqrt(num_antenna)
            x_batch_np = X_batch.detach().clone().numpy()
            x_batch_complex = x_batch_np[:,:num_antenna] + 1j*x_batch_np[:,num_antenna:]
            # z = np.matmul(x_batch_complex, learned_codebook.conj())
            # h_est = np.matmul(np.linalg.pinv(learned_codebook.conj().T),z)
            z = learned_codebook.conj().T @ x_batch_complex.T
            h_est = np.linalg.pinv(learned_codebook.conj().T) @ z
            h_est_cat = np.concatenate((h_est.real, h_est.imag),axis=0)
            var_X_batch = torch.from_numpy(h_est_cat.T).float()
            var_y_batch = y_batch.float()
            z_var = None
            if h_est_force_z:
                z_var = torch.from_numpy(z.T).float()
            optimizer.zero_grad()
            output = model(var_X_batch,z_var)
            loss = loss_fn(output, var_y_batch.unsqueeze(dim=-1))
            loss.backward()
            optimizer.step()
            train_loss += loss.detach().item()
        train_loss /= batch_idx + 1
        model.eval()
        val_loss = 0
        for batch_idx, (X_batch, y_batch) in enumerate(val_loader):
            theta = model.codebook.theta.detach().clone().numpy()
            learned_codebook = np.exp(1j*theta)/np.sqrt(num_antenna)
            x_batch_np = X_batch.detach().clone().numpy()
            x_batch_complex = x_batch_np[:,:num_antenna] + 1j*x_batch_np[:,num_antenna:]
            # z = np.matmul(x_batch_complex, learned_codebook.conj())
            # h_est = np.matmul(np.linalg.pinv(learned_codebook.conj().T),z)
            z = learned_codebook.conj().T @ x_batch_complex.T
            h_est = np.linalg.pinv(learned_codebook.conj().T) @ z
            h_est_cat = np.concatenate((h_est.real, h_est.imag),axis=0)
            var_X_batch = torch.from_numpy(h_est_cat.T).float()
            var_y_batch = y_batch.float()
            z_var = None
            if h_est_force_z:
                z_var = torch.from_numpy(z.T).float()
            output = model(var_X_batch,z_var)
            loss = loss_fn(output, var_y_batch.unsqueeze(dim=-1))
            val_loss += loss.detach().item()
        val_loss /= batch_idx + 1
        train_loss_hist.append(train_loss)
        val_loss_hist.append(val_loss)
        if epoch % 10 == 0:
            print('Epoch : {} Training loss = {:.2f}, Validation loss = {:.2f}.'.format(epoch, train_loss, val_loss))
    return train_loss_hist, val_loss_hist


def fast_adapt_est_h(batch, learner, loss, adaptation_steps, shots, h_est_force_z = False):
    data, labels = batch
    # Separate data into adaptation/evalutation sets
    adaptation_indices = np.zeros(data.shape[0], dtype=bool)
    adaptation_indices[np.arange(shots) * 2] = True
    evaluation_indices = ~adaptation_indices
    adaptation_h = data[adaptation_indices]
    adaptation_y = torch.from_numpy(data[adaptation_indices]).float()
    evaluation_h = data[evaluation_indices]
    evaluation_y = torch.from_numpy(data[evaluation_indices]).float()

    # Adapt the model
    for step in range(adaptation_steps):
        # adaptation_x = torch.from_numpy(estimate_h(adaptation_h, learner.module, num_antenna)).float() 
        adaptation_x, adaptation_z = estimate_h(adaptation_h, learner.module, num_antenna, h_est_force_z)
        adaptation_x = torch.from_numpy(adaptation_x).float()
        if h_est_force_z:
            adaptation_z = torch.from_numpy(adaptation_z).float()
        train_error = loss(learner(adaptation_x,adaptation_z), adaptation_y)
        learner.adapt(train_error)

    # Evaluate the adapted model
    # evaluation_x = torch.from_numpy(estimate_h(evaluation_h, learner.module, num_antenna)).float()  
    evaluation_x, evaluation_z = estimate_h(evaluation_h, learner.module, num_antenna, h_est_force_z)
    evaluation_x = torch.from_numpy(evaluation_x).float()
    if h_est_force_z:
        evaluation_z = torch.from_numpy(evaluation_z).float()    
    predictions = learner(evaluation_x,evaluation_z)
    valid_error = loss(predictions, evaluation_y)
    return valid_error
        
def train_est_h(train_batch, model, optimizer, loss_fn, train_steps, h_est_force_z = False):
    model.train()
    train_h,train_y = train_batch
    train_y = torch.from_numpy(train_y).float()
    train_loss = 0.0
    for step in range(train_steps):
        # train_x = torch.from_numpy(estimate_h(train_h, model, num_antenna)).float() 
        train_x, train_z = estimate_h(train_h, model, num_antenna, h_est_force_z)
        train_x = torch.from_numpy(train_x).float()
        if h_est_force_z:
            train_z = torch.from_numpy(train_z).float()
        optimizer.zero_grad()
        output = model(train_x,train_z)
        loss = loss_fn(output, train_y.unsqueeze(dim=-1))
        loss.backward()
        optimizer.step()
        train_loss += loss.detach().item()
    train_loss /= train_steps
    return train_loss

def eval_est_h(val_batch, model, loss_fn, h_est_force_z = False):
    model.eval()
    val_h,val_y = val_batch
    val_y = torch.from_numpy(val_y).float()
    # val_x = torch.from_numpy(estimate_h(val_h, model, num_antenna)).float() 
    val_x, val_z = estimate_h(val_h, model, num_antenna, h_est_force_z)
    if h_est_force_z:
        val_z = torch.from_numpy(val_z).float()
    loss = loss_fn(model(val_x,val_z),val_y)
    return loss.item()
   
    
    
       
    
    

dataset = GaussianCenters(possible_loc=loc[:,:2],
                           n_clusters=n_clusters, arrival_rate = arrival_rate, cluster_variance = cluster_variance)

test_gains_maml = np.zeros((len(num_of_beams),ntest,dataset.n_clusters*dataset.arrival_rate))
test_gains_scratch = np.zeros((len(num_of_beams),ntest,dataset.n_clusters*dataset.arrival_rate))
test_gains_dft = np.zeros((len(num_of_beams),ntest,dataset.n_clusters*dataset.arrival_rate))

for i,N in enumerate(num_of_beams):
    print(str(N) + '-beams Codebook')
    
    # Model:
    # ------
    model = AnalogBeamformer(n_antenna = num_antenna, n_beam = N)
    maml = MAML(model, lr=fast_lr, first_order=True)
    # Training:
    # ---------
    optimizer = optim.Adam(model.parameters(),lr=meta_lr, betas=(0.9,0.999), amsgrad=False)
    loss_fn = bf_gain_loss

    for iteration in range(nepoch):
        optimizer.zero_grad()
        meta_train_error = 0.0
        meta_valid_error = 0.0
        for task in range(batch_size):
            dataset.change_cluster()
            # Compute meta-training loss
            learner = maml.clone()
            batch_idc = dataset.sample()
            batch = (h_concat_scaled[batch_idc,:],egc_gain_scaled[batch_idc])
            evaluation_error = fast_adapt_est_h(batch,
                                        learner,
                                        loss_fn,
                                        update_step,
                                        shots,
                                        h_est_force_z)
            evaluation_error.backward()
            meta_train_error += evaluation_error.item()
    
            # Compute meta-validation loss
            learner = maml.clone()
            batch_idc = dataset.sample()
            batch = (h_concat_scaled[batch_idc,:],egc_gain_scaled[batch_idc])
            evaluation_error = fast_adapt_est_h(batch,
                                        learner,
                                        loss_fn,
                                        update_step,
                                        shots,
                                        h_est_force_z)
            meta_valid_error += evaluation_error.item()
    
        # Print some metrics
        print('\n')
        print('Iteration', iteration)
        print('Meta Train Loss', meta_train_error / batch_size)
        print('Meta Valid Loss', meta_valid_error / batch_size)
    
        # Average the accumulated gradients and optimize
        for p in maml.parameters():
            p.grad.data.mul_(1.0 / batch_size)
        optimizer.step()
    
        if iteration % 50 == 0:
            maml_bf_gains_val = []
            scratch_bf_gains_val = []
            dft_bf_gains_val = []
            
            for test_iter in range(nval):
                dataset.change_cluster()
                sample_idc_train = dataset.sample()
                x_train = h_concat_scaled[sample_idc_train,:]
                y_train = egc_gain_scaled[sample_idc_train]
            
                # model_maml = maml.module.clone()
                model_maml = AnalogBeamformer(n_antenna = num_antenna, n_beam = N, theta = torch.from_numpy(maml.module.codebook.theta.detach().clone().numpy()))
                opt_maml_model = optim.Adam(model_maml.parameters(),lr=fast_lr, betas=(0.9,0.999), amsgrad=False)
                train_loss_maml = train_est_h((x_train,y_train), model_maml, opt_maml_model, loss_fn, update_step, h_est_force_z)
                maml_theta = model_maml.codebook.theta.detach().clone().numpy()
                maml_codebook = np.exp(1j*maml_theta)/np.sqrt(num_antenna)       
                
                model_scratch = AnalogBeamformer(n_antenna = num_antenna, n_beam = N)
                opt_scratch_model = optim.Adam(model_scratch.parameters(),lr=fast_lr, betas=(0.9,0.999), amsgrad=False)
                train_loss_scratch = train_est_h((x_train,y_train), model_scratch, opt_scratch_model, loss_fn, update_step, h_est_force_z)
                scratch_theta = model_scratch.codebook.theta.detach().clone().numpy()
                scratch_codebook = np.exp(1j*scratch_theta)/np.sqrt(num_antenna)
            
                sample_idc_test = dataset.sample()
                x_test = h_concat_scaled[sample_idc_test,:]
                y_test = egc_gain_scaled[sample_idc_test]
                maml_bf_gains_val.extend(np.max(np.power(np.absolute(np.matmul(h[sample_idc_test,:], maml_codebook.conj())),2),axis=1))
                scratch_bf_gains_val.extend(np.max(np.power(np.absolute(np.matmul(h[sample_idc_test,:], scratch_codebook.conj())),2),axis=1))
                dft_bf_gains_val.extend(np.max(np.power(np.absolute(np.matmul(h[sample_idc_test,:], np.transpose(np.conj(DFT_codebook(N,num_antenna))))),2),axis=1))
              
            maml_bf_gains_val = 10*np.log10(maml_bf_gains_val)
            scratch_bf_gains_val = 10*np.log10(scratch_bf_gains_val)
            dft_bf_gains_val = 10*np.log10(dft_bf_gains_val)
            fig,ax = plt.subplots(figsize=(8,6))
            ax.hist(maml_bf_gains_val,bins=100,density=True,cumulative=True,histtype='step',label='MAML, {} beams'.format(num_of_beams[i]))    
            ax.hist(scratch_bf_gains_val,bins=100,density=True,cumulative=True,histtype='step',label='Learned from scratch, {} beams'.format(num_of_beams[i]))
            ax.hist(dft_bf_gains_val,bins=100,density=True,cumulative=True,histtype='step',label='DFT codebook,{} beams'.format(num_of_beams[i]))
            # tidy up the figure
            ax.grid(True)
            ax.legend(loc='upper left')
            #ax.set_title('Cumulative step histograms')
            ax.set_xlabel('BF Gain (dB)')
            ax.set_ylabel('Emperical CDF')
            ax.set_title('Codebook comparison with {} beams, Epoch {}.'.format(N, iteration))
            plt.show()
        
    for test_iter in range(ntest):
        dataset.change_cluster()
        sample_idc_train = dataset.sample()
        x_train = h_concat_scaled[sample_idc_train,:]
        y_train = egc_gain_scaled[sample_idc_train]
    
        # model_maml = maml.module.clone()
        model_maml = AnalogBeamformer(n_antenna = num_antenna, n_beam = N, theta = torch.from_numpy(maml.module.codebook.theta.clone().detach().numpy()))
        opt_maml_model = optim.Adam(model_maml.parameters(),lr=fast_lr, betas=(0.9,0.999), amsgrad=False)
        train_loss_maml = train_est_h((x_train,y_train), model_maml, opt_maml_model, loss_fn, update_step, h_est_force_z)
        maml_theta = model_maml.codebook.theta.clone().detach().numpy()
        maml_codebook = np.exp(1j*maml_theta)/np.sqrt(num_antenna)       
        
        model_scratch = AnalogBeamformer(n_antenna = num_antenna, n_beam = N)
        opt_scratch_model = optim.Adam(model_scratch.parameters(),lr=fast_lr, betas=(0.9,0.999), amsgrad=False)
        train_loss_scratch = train_est_h((x_train,y_train), model_scratch, opt_scratch_model, loss_fn, update_step, h_est_force_z)
        scratch_theta = model_scratch.codebook.theta.clone().detach().numpy()
        scratch_codebook = np.exp(1j*scratch_theta)/np.sqrt(num_antenna)
        
        sample_idc_test = dataset.sample()
        x_test = h_concat_scaled[sample_idc_test,:]
        y_test = egc_gain_scaled[sample_idc_test]
        test_gains_maml[i,test_iter,:] = np.max(np.power(np.absolute(np.matmul(h[sample_idc_test,:], maml_codebook.conj())),2),axis=1)
        test_gains_scratch[i,test_iter,:] = np.max(np.power(np.absolute(np.matmul(h[sample_idc_test,:], scratch_codebook.conj())),2),axis=1)
        test_gains_dft[i,test_iter,:] = np.max(np.power(np.absolute(np.matmul(h[sample_idc_test,:], np.transpose(np.conj(DFT_codebook(N,num_antenna))))),2),axis=1)

test_gains_maml = 10*np.log10(test_gains_maml)   
test_gains_scratch = 10*np.log10(test_gains_scratch)   
test_gains_dft = 10*np.log10(test_gains_dft) 

for i, N in enumerate(num_of_beams):
    fig,ax = plt.subplots(figsize=(8,6))
    ax.hist(test_gains_maml[i,:,:].flatten(),bins=100,density=True,cumulative=True,histtype='step',label='MAML, {} beams'.format(num_of_beams[i]))    
    ax.hist(test_gains_scratch[i,:,:].flatten(),bins=100,density=True,cumulative=True,histtype='step',label='Learned from scratch, {} beams'.format(num_of_beams[i]))
    ax.hist(test_gains_dft[i,:,:].flatten(),bins=100,density=True,cumulative=True,histtype='step',label='DFT codebook,{} beams'.format(num_of_beams[i]))
    # tidy up the figure
    ax.grid(True)
    ax.legend(loc='upper left')
    #ax.set_title('Cumulative step histograms')
    ax.set_xlabel('BF Gain (dB)')
    ax.set_ylabel('Emperical CDF')
    ax.set_title('Codebook comparison with {} beams, Epoch {}.'.format(N, iteration))
    plt.show()
    
# for i, N in enumerate(num_of_beams):
#     for test_iter in range(ntest):
#         fig,ax = plt.subplots(figsize=(8,6))
#         ax.hist(test_gains_maml[i,test_iter,:],bins=100,density=True,cumulative=True,histtype='step',label='MAML, {} beams'.format(num_of_beams[i]))    
#         ax.hist(test_gains_scratch[i,test_iter,:],bins=100,density=True,cumulative=True,histtype='step',label='Learned from scratch, {} beams'.format(num_of_beams[i]))
#         ax.hist(test_gains_dft[i,test_iter,:],bins=100,density=True,cumulative=True,histtype='step',label='DFT codebook,{} beams'.format(num_of_beams[i]))
#         # tidy up the figure
#         ax.grid(True)
#         ax.legend(loc='upper left')
#         #ax.set_title('Cumulative step histograms')
#         ax.set_xlabel('BF Gain (dB)')
#         ax.set_ylabel('Emperical CDF')
#         ax.set_title('Codebook comparison with {} beams, Epoch {}.'.format(N, iteration))
#         plt.show()
        
plt.figure(figsize=(8,6))
plt.plot(num_of_beams,[test_gains_maml[i,:,:].mean() for i in range(len(num_of_beams))], marker='+',label='MAML, GD w/. est. h')    
plt.plot(num_of_beams,[test_gains_scratch[i,:,:].mean() for i in range(len(num_of_beams))],marker = 's', label='Learned from scratch, GD w/. est. h')    
plt.plot(num_of_beams,[test_gains_dft[i,:,:].mean() for i in range(len(num_of_beams))],marker='o', label='DFT') 
plt.xticks(num_of_beams,num_of_beams)
plt.grid(True)
plt.legend(loc='lower right')   
plt.xlabel('num of beams')
plt.ylabel('Avg. BF Gain (dB)')
plt.show()