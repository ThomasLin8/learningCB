# -*- coding: utf-8 -*-
"""
Created on Sat Jan  2 18:50:41 2021

@author: ethan
"""

import numpy as np
import matplotlib.pyplot as plt
from keras import optimizers
from keras.models import Input, Model
from complex_fc import CompFC
from auxiliary import PowerPooling
from keras import backend as K
import tensorflow as tf
tf.enable_eager_execution()
# import scipy.io as scio
# from DataPrep import dataPrep # Example of data preparing function
from sklearn.model_selection import train_test_split
import tqdm as tqdm

np.random.seed(7)
# num_of_beams = [2, 4, 8, 16, 32, 64, 96, 128]
num_of_beams = [32, 64, 128]
num_antenna = 64
# Training and testing data:
# --------------------------

batch_size = 500
#-------------------------------------------#
# Here should be the data_preparing function
# It is expected to return:
# train_inp, train_out, val_inp, and val_out
#-------------------------------------------#
h_real = np.load('D://Github Repositories/mmWave Beam Management/H_Matrices FineGrid/MISO_Static_FineGrid_Hmatrices_real.npy')[:10000]
h_imag = np.load('D://Github Repositories/mmWave Beam Management/H_Matrices FineGrid/MISO_Static_FineGrid_Hmatrices_imag.npy')[:10000]
h = h_real + 1j*h_imag
#norm_factor = np.max(np.power(abs(h),2))
norm_factor = np.max(abs(h))
h_scaled = h/norm_factor
h_concat_scaled = np.concatenate((h_real/norm_factor,h_imag/norm_factor),axis=1)
# Compute EGC gain
#egc_gain = np.power(np.sum(np.sqrt(np.power(h_real,2)+np.power(h_imag,2)),axis=1),2)/num_antenna
egc_gain_scaled = np.power(np.sum(abs(h_scaled),axis=1),2)/num_antenna
train_idc, test_idc = train_test_split(np.arange(h.shape[0]),test_size=0.4)
val_idc, test_idc = train_test_split(test_idc,test_size=0.5)
x_train,y_train = h_concat_scaled[train_idc,:],egc_gain_scaled[train_idc]
x_val,y_val = h_concat_scaled[val_idc,:],egc_gain_scaled[val_idc]
x_test,y_test = h_concat_scaled[test_idc,:],egc_gain_scaled[test_idc]
#x_train, x_test, y_train, y_test = train_test_split(h_concat_scaled,egc_gain,test_size=0.4)
#x_val, x_test, y_val, y_test = train_test_split(x_test,y_test,test_size=0.5)
def bf_gain_loss(y_true, y_pred):
    return -K.mean(y_pred,axis=-1)

num_antenna = h.shape[1]
#learned_codebook_gains = np.zeros((len(num_of_beams),len(test_idc)))
#learned_codebooks = []
#for i,N in enumerate(num_of_beams):
#    print(str(N) + '-beams Codebook')
#
#    # Model:
#    # ------
#    xBatch = Input(shape=(num_antenna*2,))
#    fc1 = CompFC(N, seed=None, scale=np.sqrt(num_antenna), activation='linear')(xBatch)
#    max_pooling = PowerPooling(2 * N)(fc1)
#    model = Model(inputs=xBatch, outputs=max_pooling)
#
#    # Training:
#    # ---------
#    adam = optimizers.Adam(lr=0.01, beta_1=0.9, beta_2=0.999, epsilon=None, decay=0, amsgrad=False)
#    model.compile(optimizer=adam, loss=bf_gain_loss)
#        
#    hist = model.fit(x_train, y_train,
#              epochs=100,
#              batch_size=batch_size,
#              shuffle=True,
#              validation_data=(x_val, y_val),verbose=0)
#    plt.figure()
#    plt.plot(-np.array(hist.history['loss']),label='train loss')
#    plt.plot(-np.array(hist.history['val_loss']),label='val loss')
#    plt.xlabel('Epochs')
#    plt.ylabel('loss')
#    plt.title('Unsupervised. {} beams'.format(N))
#    # Extract learned codebook:
#    # -------------------------
#    theta = np.array(model.get_weights()[0])
#    print(theta.shape)
#    # name_of_file = 'theta_NLOS' + str(N) + 'vec.mat'
#    # scio.savemat(name_of_file,
#    #              {'train_inp': train_inp,
#    #               'train_out': train_out,
#    #               'val_inp': val_inp,
#    #               'val_out': val_out,
#    #               'codebook': theta})
#    learned_codebook = np.exp(1j*theta)/np.sqrt(num_antenna)
#    learned_codebooks.append(learned_codebook)
#    learned_codebook_gains[i,:] = np.max(np.power(np.absolute(np.matmul(h[test_idc,:], np.conj(learned_codebook))),2),axis=1)
#learned_codebook_gains = 10*np.log10(learned_codebook_gains)

#learned_codebook_gains_supervised = np.zeros((len(num_of_beams),len(test_idc)))
#learned_codebooks_supervised = []
#for i,N in enumerate(num_of_beams):
#    print(str(N) + '-beams Codebook')
#
#    # Model:
#    # ------
#    xBatch = Input(shape=(num_antenna*2,))
#    fc1 = CompFC(N, seed=None, scale=np.sqrt(num_antenna), activation='linear')(xBatch)
#    max_pooling = PowerPooling(2 * N)(fc1)
#    model = Model(inputs=xBatch, outputs=max_pooling)
#
#    # Training:
#    # ---------
#    adam = optimizers.Adam(lr=0.01, beta_1=0.9, beta_2=0.999, epsilon=None, decay=0, amsgrad=False)
#    model.compile(optimizer=adam, loss='mse')
#        
#    hist = model.fit(x_train, y_train,
#              epochs=100,
#              batch_size=batch_size,
#              shuffle=True,
#              validation_data=(x_val, y_val),verbose=0)
#    
#    plt.figure()
#    plt.plot(hist.history['loss'],label='train loss')
#    plt.plot(hist.history['val_loss'],label='val loss')
#    plt.xlabel('Epochs')
#    plt.ylabel('loss')
#    plt.title('Supervised. {} beams'.format(N))
#    # Extract learned codebook:
#    # -------------------------
#    theta = np.array(model.get_weights()[0])
#    print(theta.shape)
#    # name_of_file = 'theta_NLOS' + str(N) + 'vec.mat'
#    # scio.savemat(name_of_file,
#    #              {'train_inp': train_inp,
#    #               'train_out': train_out,
#    #               'val_inp': val_inp,
#    #               'val_out': val_out,
#    #               'codebook': theta})
#    learned_codebook = np.exp(1j*theta)/np.sqrt(num_antenna)
#    learned_codebooks_supervised.append(learned_codebook)
#    learned_codebook_gains_supervised[i,:] = np.max(np.power(np.absolute(np.matmul(h[test_idc,:], np.conj(learned_codebook))),2),axis=1)
#learned_codebook_gains_supervised = 10*np.log10(learned_codebook_gains_supervised)

#-------------------------------------------#
# Comppare between learned codebook and DFT codebook on test set
#-------------------------------------------#    
def DFT_codebook(nseg,n_antenna):
    bfdirections = np.arccos(np.linspace(np.cos(0),np.cos(np.pi-1e-6),nseg))
    codebook_all = np.zeros((nseg,n_antenna),dtype=np.complex_)
    for i in range(nseg):
        phi = bfdirections[i]
        #array response vector original
        arr_response_vec = [-1j*np.pi*k*np.cos(phi) for k in range(n_antenna)]
        #array response vector for rotated ULA
        #arr_response_vec = [1j*np.pi*k*np.sin(phi+np.pi/2) for k in range(64)]
        codebook_all[i,:] = np.exp(arr_response_vec)/np.sqrt(n_antenna)
    return codebook_all

dft_gains = np.zeros((len(num_of_beams),len(test_idc)))
for i, nbeams in enumerate(num_of_beams):
    dft_gains[i,:] = np.max(np.power(np.absolute(np.matmul(h[test_idc,:], np.transpose(np.conj(DFT_codebook(nbeams,num_antenna))))),2),axis=1)
dft_gains = 10*np.log10(dft_gains)

#fig,ax = plt.subplots(figsize=(8,6))
#for i in range(len(num_of_beams)):
#    ax.hist(learned_codebook_gains[i,:],bins=100,density=True,cumulative=True,histtype='step',label='learned codebook, {} beams'.format(num_of_beams[i]))    
#    ax.hist(dft_gains[i,:],bins=100,density=True,cumulative=True,histtype='step',label='DFT codebook,{} beams'.format(num_of_beams[i]))
## tidy up the figure
#ax.grid(True)
#ax.legend(loc='upper left')
##ax.set_title('Cumulative step histograms')
#ax.set_xlabel('BF Gain (dB)')
#ax.set_ylabel('Emperical CDF')
#plt.show()

train_set = tf.data.Dataset.from_tensor_slices((x_train))
train_set = train_set.shuffle(buffer_size=1024).batch(batch_size)
val_set = tf.data.Dataset.from_tensor_slices((x_val))
val_set = val_set.shuffle(buffer_size=1024).batch(batch_size)

learned_codebook_gains_genius = np.zeros((len(num_of_beams),len(test_idc)))
learned_codebooks_genius = []

for i,N in enumerate(num_of_beams):
    print(str(N) + '-beams Codebook')

    # Model:
    # ------
    xBatch = Input(shape=(num_antenna*2,))
    fc1 = CompFC(N, seed=None, scale=np.sqrt(num_antenna), activation='linear')(xBatch)
    max_pooling = PowerPooling(2 * N)(fc1)
    model = Model(inputs=xBatch, outputs=max_pooling)

    # Training:
    # ---------
    adam = optimizers.Adam(lr=0.01, beta_1=0.9, beta_2=0.999, epsilon=None, decay=0, amsgrad=False)
    nepochs = 100
    train_loss_history = []
    val_loss_history = []
    for epoch in range(nepochs):
#        pbar_train = tqdm(range(len(train_set)))
        train_loss_epoch = 0
        for step, x_train_batch in enumerate(train_set):
            codebook = np.exp(1j*np.array(model.get_weights()[0]))/np.sqrt(num_antenna)
            z = np.matmul(x_train_batch, np.matrix(codebook).H)
            h_est = np.matmul(np.linalg.pinv(np.matrix(codebook).H),z)
            h_est_tensor = K.constant(h_est)
            with tf.GradientTape() as tape:
                g = model(h_est_tensor,training=True)
                loss_value = -K.mean(g,axis=-1)
            grads = tape.gradient(loss_value, model.trainable_weights)
            adam.apply_gradients(zip(grads,model.trainable_weights))
            train_loss_epoch += float(loss_value)
#            pbar_train.set_description('Train Loss: %.3f' % float(loss_value))
        train_loss_history.append(train_loss_epoch)
        val_loss_epoch = 0
        for step, x_val_batch in enumerate(val_set):
            g = model(x_val_batch, training=False)
            val_loss_epoch += float(-K.mean(g,axis=-1))
        val_loss_history.append(val_loss_history)
        print('Epoch # {}, train loss = {}, val loss = {}'.format(epoch,train_loss_epoch,val_loss_epoch))
              
    plt.figure()
    plt.plot(train_loss_history,label='train loss')
    plt.plot(val_loss_history,label='val loss')
    plt.xlabel('Epochs')
    plt.ylabel('loss')
    plt.title('My Genius. {} beams'.format(N))
    # Extract learned codebook:
    # -------------------------
    theta = np.array(model.get_weights()[0])
    print(theta.shape)
    # name_of_file = 'theta_NLOS' + str(N) + 'vec.mat'
    # scio.savemat(name_of_file,
    #              {'train_inp': train_inp,
    #               'train_out': train_out,
    #               'val_inp': val_inp,
    #               'val_out': val_out,
    #               'codebook': theta})
    learned_codebook_genius = np.exp(1j*theta)/np.sqrt(num_antenna)
    learned_codebooks_genius.append(learned_codebook_genius)
    learned_codebook_gains_genius[i,:] = np.max(np.power(np.absolute(np.matmul(h[test_idc,:], np.conj(learned_codebook_genius))),2),axis=1)
learned_codebook_gains_genius = 10*np.log10(learned_codebook_gains_genius)
        
for i in range(len(num_of_beams)):
    fig,ax = plt.subplots(figsize=(8,6))
#    ax.hist(learned_codebook_gains[i,:],bins=100,density=True,cumulative=True,histtype='step',label='unsupervised, {} beams'.format(num_of_beams[i]))    
#    ax.hist(learned_codebook_gains_supervised[i,:],bins=100,density=True,cumulative=True,histtype='step',label='supervised, {} beams'.format(num_of_beams[i]))
    ax.hist(learned_codebook_gains_genius[i,:],bins=100,density=True,cumulative=True,histtype='step',label='genius, {} beams'.format(num_of_beams[i]))
    ax.hist(dft_gains[i,:],bins=100,density=True,cumulative=True,histtype='step',label='dft, {} beams'.format(num_of_beams[i]))
    # tidy up the figure
    ax.grid(True)
    ax.legend(loc='upper left')
    #ax.set_title('Cumulative step histograms')
    ax.set_xlabel('BF Gain (dB)')
    ax.set_ylabel('Emperical CDF')
    plt.show()
    

