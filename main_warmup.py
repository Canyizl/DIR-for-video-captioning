import os
import pickle
import torch
import torch.nn as nn
from torch import optim
import torch.nn.functional as F
from torch.optim.lr_scheduler import StepLR

import warnings
warnings.filterwarnings('ignore')

from utils import Utils,get_w2v_vec,get_datetime_stamp,get_user_yesno_answer,Vocabulary
from data.data import get_train_loader,get_eval_loader
from data.opt import parse_opt
from train import train

import sys
import json
from gensim.models import KeyedVectors
from models.Encoder import EncoderVisual
from models.Decoder import Decoder
from models.model2 import MLP,Reason
from torch.optim.lr_scheduler import StepLR

#set seed for reproducibility
utils = Utils()
utils.set_seed(1)
#Import configuration and model
from early_stopper import EarlyStopper
from config import ConfigMARN

def main():
    #create Mean pooling object
    cfg = ConfigMARN()
    cfg.dataset = 'msrvtt'
    vocab_pkl_path = "./dataset/MSR-VTT/msr-vtt_vocab.pkl"
    with open(vocab_pkl_path, 'rb') as f:
        vocab = pickle.load(f)
    cfg.vocab_size = len(vocab)
    print("vocab_size:",cfg.vocab_size)
    # Datasets and dataloaders
    json_path = f"msrvtt_final.json"
    with open(json_path) as f:
        json_data = json.load(f)

    cfg.batch_size = 16
    inds,relations,json_data_list = json_data['inds'],json_data['relations'],json_data['dataset']

    cfg.len_inds = len(inds)
    cfg.len_rels = len(relations)

    json_data_dict = {dp['video_id']: dp for dp in json_data_list}
    train_loader = get_train_loader(cfg,json_data_dict,'./dataset/MSR-VTT/msr-vtt_captions_train.pkl','./dataset/MSR-VTT/msr-vtt_features.h5')
    test_loader = None
    test_reference = None

    exp_name = get_datetime_stamp()
    exp_dir = os.path.join(cfg.data_dir, exp_name)
    if not os.path.isdir(exp_dir):
        os.makedirs(exp_dir)
        print("makedirs")

    cfg.dict_path = '../dict2.pt'

    if cfg.dict_path:
        save_model = torch.load(cfg.dict_path)
        ind_dict = save_model['ind_dict']
        rel_dict = save_model['rel_dict']

    cfg.reload = None
    if cfg.reload:
        reload_file_path = cfg.reload
        print('Reloading model from {}'.format(reload_file_path))
        saved_model = torch.load(reload_file_path)
        encoder = saved_model['encoder']
        mul_ind = saved_model['mul_ind']
        mul_rel = saved_model['mul_rel']
        encoder.batch_size = cfg.batch_size
        best_loss = saved_model['best_metrics']
        reason_ind = saved_model['reason_ind']
        reason_rel = saved_model['reason_rel']
        #reason_ind = Reason(cfg.word_size,cfg.word_size,cfg.reason_size).to(cfg.device)
        #reason_rel = Reason(cfg.word_size,cfg.word_size,cfg.reason_size).to(cfg.device)
        #decoder = Decoder(cfg, vocab).to(cfg.device)
        decoder = saved_model['decoder']
    else:
        print('Initializing new networks...')
        encoder = EncoderVisual(cfg).to(cfg.device)
        mul_ind = MLP(cfg.appearance_projected_size,cfg.reason_size, cfg.len_inds).to(cfg.device)
        mul_rel = MLP(cfg.motion_projected_size,cfg.reason_size,cfg.len_rels).to(cfg.device)
        best_loss = None
        reason_ind = Reason(cfg.word_size,cfg.word_size,cfg.reason_size).to(cfg.device)
        reason_rel = Reason(cfg.word_size,cfg.word_size,cfg.reason_size).to(cfg.device)
        decoder = Decoder(cfg,vocab).to(cfg.device)

    params_list = [encoder.parameters(), mul_ind.parameters(),mul_rel.parameters()]
    optimizer = optim.Adam([{'params': params, 'lr': cfg.learning_rate, 'wd': cfg.weight_decay} for params in params_list])
    #optimizer = optim.SGD([{'params': params, 'lr': cfg.learning_rate, 'wd': cfg.weight_decay,'momentum':0.9} for params in params_list])
    sched = StepLR(optimizer,step_size = 5, gamma = 0.33,last_epoch = -1)
    print('\nTraining the model')
    training = True
    #best_loss = 0.84495
    train(cfg, inds, relations, encoder, mul_ind, mul_rel, reason_ind, reason_rel, decoder, train_loader, test_loader,
          optimizer, sched, exp_name, training, best_loss, ind_dict, rel_dict, test_reference)
    #from train import evaluate
    #metrics = evaluate(cfg,encoder,mul_ind,mul_rel,reason_ind,reason_rel,decoder,inds,ind_dict,relations,rel_dict,test_loader,test_reference)
    #print(metrics)
if __name__ == '__main__':
    main()

