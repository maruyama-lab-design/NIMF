#!/usr/bin/env python3

import argparse, os, sys, time, shutil, tqdm
import warnings, json, gzip
import numpy as np
from sklearn.model_selection import GroupKFold

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
from torch.utils.data import DataLoader, Subset

import matplotlib.pyplot as plt

import epi_models
import epi_dataset
import misc_utils


import functools
from sklearn import metrics

import pandas as pd 
import pickle
import glob


print = functools.partial(print, flush=True)



def model_summary(model):
	"""
	model: pytorch model
	"""
	import torch
	total_param = 0
	trainable_param = 0
	for i, p in enumerate(model.parameters()):
		num_p = torch.numel(p)
		if p.requires_grad:
			trainable_param += num_p
		total_param += num_p
	return {'total_param': total_param, 'trainable_param': trainable_param}




def predict(model: nn.Module, data_loader: DataLoader, device=torch.device('cuda'), save_final_feat=False, research_name=None):
	model.eval()
	result, true_label, result_dist, true_dist = list(), list(), list(), list()
	for batch_idx, (feats, dists, enh_idxs, prom_idxs, labels) in enumerate(data_loader):

		feats, dists, labels = feats.to(device), dists.to(device), labels.to(device)
		# enh_idxs, prom_idxs = enh_idxs.to(device), prom_idxs.to(device)
		pred, pred_dist, att = model(feats, return_att=True, enh_idx=enh_idxs, prom_idx=prom_idxs, batch_idx=batch_idx,
									 save_final_feat=save_final_feat, research_name=research_name)
		del att
		pred = pred.detach().cpu().numpy()
		labels = labels.detach().cpu().numpy()
		pred_dist = pred_dist.detach().cpu().numpy()
		dists = dists.detach().cpu().numpy()
		result.append(pred)
		true_label.append(labels)
		result_dist.append(pred_dist)
		true_dist.append(dists)
	result = np.concatenate(result, axis=0)
	true_label = np.concatenate(true_label, axis=0)
	result_dist = np.concatenate(result_dist, axis=0)
	true_dist = np.concatenate(true_dist, axis=0)
	return (result.squeeze(), true_label.squeeze(), result_dist.squeeze(), true_dist.squeeze())


def train(
		model_class, model_params, 
		optimizer_class, optimizer_params, 
		dataset, groups,
		num_epoch, patience, batch_size, num_workers,
		outdir, model_name, checkpoint_prefix, device, 
		train_chroms, valid_chroms,
		use_scheduler=False,) -> nn.Module:

	bce_loss = nn.BCELoss() # binary cross entropy

	wait = 0
	best_epoch, best_val_auc, best_val_aupr = -999, -999, -999
	best_loss = 999
	epoch_results = {"AUC": list(), "AUPR": list()}

	loss_dict = {"epochs": [], "train_loss": [], "valid_loss": []}
	train_idx, valid_idx = [], []

	for epoch_idx in range(num_epoch):

		epoch_results["AUC"] = 0
		epoch_results["AUPR"] = 0

		if epoch_idx == 0:
			for idx, chrom in enumerate(groups):
				if chrom in train_chroms:
					train_idx.append(idx)
				elif chrom in valid_chroms:
					valid_idx.append(idx)
			print("  - validation size:{}({}) training size:{}({})".format(len(valid_idx), misc_utils.count_unique_itmes(groups[valid_idx]), len(train_idx), misc_utils.count_unique_itmes(groups[train_idx])))

				

		print("\nCV epoch: {}/{}\t({})".format(epoch_idx, num_epoch, time.asctime()))
		

		modeldir = os.path.join(os.path.dirname(__file__), outdir, "model", model_name)
		os.makedirs(modeldir, exist_ok = True)
		
		with open(os.path.join(modeldir, "log.txt"), "a") as f:
			print("  epochs{}: validation size:{}({}) training size:{}({})".format(epoch_idx, len(valid_idx), misc_utils.count_unique_itmes(groups[valid_idx]), len(train_idx), misc_utils.count_unique_itmes(groups[train_idx])), file=f)

		train_loader = DataLoader(Subset(dataset, indices=train_idx), shuffle=True, batch_size=batch_size, num_workers=num_workers)
		sample_idx = np.random.permutation(train_idx)[0:1024]
		sample_loader = DataLoader(Subset(dataset, indices=sample_idx), shuffle=False, batch_size=batch_size, num_workers=num_workers)
		valid_loader = DataLoader(Subset(dataset, indices=valid_idx), shuffle=False, batch_size=batch_size, num_workers=num_workers)
		checkpoint = "{}/{}.pt".format(modeldir, checkpoint_prefix)
		if epoch_idx == 0:
			model = model_class(**model_params).to(device)
			optimizer = optimizer_class(model.parameters(), **optimizer_params)
			scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(optimizer, T_0=5, T_mult=2)
			if os.path.exists(checkpoint):
				os.remove(checkpoint)
		else:
			state_dict = torch.load(checkpoint)
			model.load_state_dict(state_dict["model_state_dict"])
			optimizer.load_state_dict(state_dict["optimizer_state_dict"])
			scheduler.load_state_dict(state_dict["scheduler_state_dict"])

		model.train()
		for feats, dists, enh_idxs, prom_idxs, labels in tqdm.tqdm(train_loader): # train by batch

			feats, dists, labels = feats.to(device), dists.to(device), labels.to(device)
			if hasattr(model, "att_C"): # TODO
				pred, pred_dists, att = model(feats, return_att=True, enh_idx=enh_idxs, prom_idx=prom_idxs)
				attT = att.transpose(1, 2)
				identity = torch.eye(att.size(1)).to(device)
				identity = Variable(identity.unsqueeze(0).expand(labels.size(0), att.size(1), att.size(1)))
				penal = model.l2_matrix_norm(torch.matmul(att, attT) - identity)

				loss = bce_loss(pred, labels) + (model.att_C * penal / labels.size(0)).type(torch.cuda.FloatTensor)

				del penal, identity
			else:
				pred = model(feats, enh_idx=enh_idxs, prom_idx=prom_idxs)
				loss = bce_loss(pred, labels)

			optimizer.zero_grad()
			loss.backward()
			optimizer.step()



		# prepare for next epoch
		if use_scheduler:
			scheduler.step()

		torch.save({
			"model_state_dict": model.state_dict(),
			"optimizer_state_dict": optimizer.state_dict(),
			"scheduler_state_dict": scheduler.state_dict()
		}, checkpoint)

		torch.save({
			"model_state_dict": model.state_dict(),
			"optimizer_state_dict": optimizer.state_dict(),
			"scheduler_state_dict": scheduler.state_dict()
		}, os.path.join(modeldir, f"epoch{epoch_idx}.pt"))

		model.eval()
		train_loss, valid_loss = None, None
		train_pred, train_true, train_pred_dist, train_true_dist = predict(model, sample_loader)
		tra_AUC, tra_AUPR, tra_F1, tra_pre, tra_rec, tra_MCC = misc_utils.evaluator(train_true, train_pred, out_keys=["AUC", "AUPR", "F1", "precision", "recall", "MCC"])
		valid_pred, valid_true, valid_pred_dist, valid_true_dist = predict(model, valid_loader)
		val_AUC, val_AUPR, val_F1, val_pre, val_rec, val_MCC = misc_utils.evaluator(valid_true, valid_pred, out_keys=["AUC", "AUPR", "F1", "precision", "recall", "MCC"])

		train_loss = metrics.log_loss(train_true, train_pred.astype(np.float64))
		valid_loss = metrics.log_loss(valid_true, valid_pred.astype(np.float64))

		log_tra_text = f"  - train...\nloss={train_loss:.4f}\tAUC={tra_AUC:.4f}\tAUPR={tra_AUPR:.4f}\tF1={tra_F1:.4f}\tpre={tra_pre:.4f}\trec={tra_rec:.4f}\tMCC={tra_MCC:.4f}\t"
		log_val_text = f"  - valid...\nloss={valid_loss:.4f}\tAUC={val_AUC:.4f}\tAUPR={val_AUPR:.4f}\tF1={val_F1:.4f}\tpre={val_pre:.4f}\trec={val_rec:.4f}\tMCC={val_MCC:.4f}\t"
		print(log_tra_text)
		print(log_val_text)

		with open(os.path.join(modeldir, "log.txt"), "a") as f:
			print(f"___epochs{epoch_idx}___", file=f)
			print(log_tra_text, file=f)
			print(log_val_text, file=f)


		epoch_results["AUC"] = val_AUC
		epoch_results["AUPR"] = val_AUPR

		loss_dict["epochs"].append(epoch_idx)
		loss_dict["train_loss"].append(train_loss)
		loss_dict["valid_loss"].append(valid_loss)


		auc_mean, auc_std = epoch_results["AUC"], epoch_results["AUC"]
		aupr_mean, aupr_std = epoch_results["AUPR"], epoch_results["AUPR"]
		print("Epoch{:03d}(AUC/AUPR):\t{:.4f}({:.4f})\t{:.4f}({:.4f})".format(epoch_idx, auc_mean, auc_std, aupr_mean, aupr_std))

		# if auc_mean >= best_val_auc and aupr_mean >= best_val_aupr:
		if valid_loss <= best_loss:
			wait = 0
			best_loss = valid_loss
			best_epoch, best_val_auc, best_val_aupr = epoch_idx, auc_mean, aupr_mean
			print("Best epoch {}\t({})".format(best_epoch, time.asctime()))
		else:
			wait += 1
			if wait >= patience:
				print("Early stopped ({})".format(time.asctime()))
				print("Best epoch/AUC/AUPR: {}\t{:.4f}\t{:.4f}".format(best_epoch, best_val_auc, best_val_aupr))
				break
			else:
				print("Wait{} ({})".format(wait, time.asctime()))


	# save best model
	print(f"best epoch is {best_epoch}")
	best_model_path = os.path.join(modeldir, f"epoch{best_epoch}.pt")
	shutil.copyfile(best_model_path, os.path.join(modeldir, f"best_epoch.pt"))



def test(model_class, model_params, 
		optimizer_class, optimizer_params, 
		dataset, groups, test_chroms, batch_size, num_workers, outpath, model_path):

	print(f"loading {model_path}...")
	model = model_class(**model_params).to(device)
	optimizer = optimizer_class(model.parameters(), **optimizer_params)
	state_dict = torch.load(model_path)
	model.load_state_dict(state_dict["model_state_dict"])
	optimizer.load_state_dict(state_dict["optimizer_state_dict"])

	test_idx = []
	for idx, chrom in enumerate(groups):
		if chrom in test_chroms:
			test_idx.append(idx)
	chroms = np.array(dataset.metainfo["chrom"])[test_idx]
	distances = np.array(dataset.metainfo["dist"])[test_idx]
	enh_names = np.array(dataset.metainfo["enh_name"])[test_idx]
	prom_names = np.array(dataset.metainfo["prom_name"])[test_idx]
	test_loader = DataLoader(Subset(dataset, indices=test_idx), shuffle=False, batch_size=batch_size, num_workers=num_workers)
	model.eval()
	test_pred, test_true, test_pred_dist, test_true_dist = predict(model, test_loader)
	# AUC, AUPR, F_in, pre, rec, MCC = misc_utils.evaluator(test_true, test_pred, out_keys=["AUC", "AUPR", "F1", "precision", "recall", "MCC"])

	np.savetxt(
			os.path.join(outpath),
			np.concatenate((
				test_true.reshape(-1, 1).astype(int).astype(str),
				test_pred.reshape(-1, 1).round(4).astype(str),
				chroms.reshape(-1, 1),
				distances.reshape(-1, 1).astype(int).astype(str),
				enh_names.reshape(-1, 1),
				prom_names.reshape(-1, 1)
			), axis=1),
			delimiter='\t',
			fmt="%s",
			comments="",
			header="true\tpred\tchrom\tdistance\tenhancer_name\tpromoter_name"
	)

	




def get_args():
	p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	p.add_argument('--gpu', default=1, type=int, help="GPU ID, (-1 for CPU)")
	p.add_argument('--seed', type=int, default=2020, help="Random seed")
	p.add_argument('--train_cell', type=str, default="GM12878", help="cell line on train")
	p.add_argument('--test_cell', type=str, default="GM12878", help="cell line on test")
	p.add_argument('--config', type=str, default="chromosomal_cross_validation.json", help="config filename")

	# 以下追加
	p.add_argument('--use_mse', action="store_true")
	p.add_argument('--test_on_another_data', action="store_true")
	# ___
	return p


if __name__ == "__main__":
	p = get_args()
	args = p.parse_args()
	np.random.seed(args.seed)
	torch.manual_seed(args.seed)

	# mse
	args.use_mse = False
	# ___

	config = json.load(open(os.path.join(os.path.dirname(__file__), args.config)))


	# args.test_on_another_data = True
	train_dir = config["train_opts"]["train_dir"]
	train_file = os.path.join(train_dir, f"{args.train_cell}.csv")

	all_train_data = epi_dataset.EPIDataset(
		datasets=train_file,
		feats_config=config["feats_config"],
		feats_order=config["feats_order"], 
		seq_len=config["seq_len"], 
		bin_size=config["bin_size"], 
		use_mark=False,
		mask_neighbor=True, # TODO
		mask_window=True, # TODO
		sin_encoding=False,
		rand_shift=False,
	)

	test_dir = config["train_opts"]["test_dir"]
	test_file = os.path.join(test_dir, f"{args.test_cell}.csv")
	
	all_test_data = epi_dataset.EPIDataset(
		datasets=test_file,
		feats_config=config["feats_config"],
		feats_order=config["feats_order"], 
		seq_len=config["seq_len"], 
		bin_size=config["bin_size"], 
		use_mark=False,
		mask_neighbor=True, # TODO
		mask_window=True, # TODO
		sin_encoding=False,
		rand_shift=False,
	)

	config["model_opts"]["in_dim"] = all_train_data.feat_dim
	config["model_opts"]["seq_len"] = config["seq_len"] // config["bin_size"] # TODO
	chroms = all_train_data.metainfo["chrom"]


	if args.gpu >= 0:
		os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
		device = torch.device("cuda")
	else:
		device = torch.device('cpu')

	model_class = getattr(epi_models, config["model_opts"]["model"])
	optimizer_params = {'lr': config["train_opts"]["learning_rate"], 'weight_decay': 1e-8}

	chrom_split = json.load(open(os.path.join(os.path.dirname(__file__), "chromosome_split_opt.json")))
	# k-fold chromosomal cross-validation
	for k in range(10):
		outdir = config["outdir"] + f"/fold{k}"

		# ___make model_name___
		model_name = ""

		# mask??
		if config["use_mask"] == True:
			model_name += "masked_"
		else:
			model_name += "no_masked_"

		print(config["train_opts"]["train_dir"])
		print(config["train_opts"]["train_dir"].split(".")[-1].split("/"))
		data, nimf = config["train_opts"]["train_dir"].split(".")[-1].split("/")[-2:]
		# BENGI or TargetFinder ??
		if data == "BENGI":
			model_name += "BG_"
		elif data == "TargetFinder":
			model_name += "TF_"
		else:
			model_name += "OT_"

		# original or NIMF ??
		if nimf == "original":
			model_name += "org_"
		elif nimf == "NIMF_9999999999":
			model_name += "INF_"
		else:
			model_name += str(nimf.split("_")[-1]) + "_"

		# which cell ??
		model_name += args.train_cell
		# ___

		os.makedirs(outdir, exist_ok=True)

		# !!!
		if os.path.exists(os.path.join(os.path.dirname(__file__), outdir, "model", model_name, f"best_epoch.pt")):
			train_mode = False
			print(f"skip train phase")
		else:
			train_mode = True


		# __train__
		if train_mode == True:
			train(
					model_class=model_class, 
					model_params=config["model_opts"],
					optimizer_class=torch.optim.Adam, 
					optimizer_params=optimizer_params,
					dataset=all_train_data,
					groups=all_train_data.metainfo["chrom"],
					num_epoch=config["train_opts"]["num_epoch"], 
					patience=config["train_opts"]["patience"], 
					batch_size=config["train_opts"]["batch_size"], 
					num_workers=config["train_opts"]["num_workers"],
					outdir=outdir,
					model_name=model_name,
					checkpoint_prefix="checkpoint",
					device=device,
					train_chroms=chrom_split[f"fold{k}"]["train_chroms"],
					valid_chroms=chrom_split[f"fold{k}"]["valid_chroms"],
					use_scheduler=config["train_opts"]["use_scheduler"],
			)




		# ___test___


		# __make pred_name__
		pred_name = ""

		# mask??
		if config["use_mask"] == True:
			pred_name += "masked_"
		else:
			pred_name += "no_masked_"

		data, nimf= config["train_opts"]["test_dir"].split(".")[-1].split("/")[-2:]
		# BENGI or TargetFinder ??
		if data == "BENGI":
			pred_name += "BG_"
		elif data == "TargetFinder":
			pred_name += "TF_"
		else:
			pred_name += "OT_"

		# original or NIMF ??
		if nimf == "original":
			pred_name += "org_"
		elif nimf == "NIMF_9999999999":
			pred_name += "INF_"
		elif "NIMF" in nimf:
			pred_name += str(nimf.split("_")[-1]) + "_"
		elif "cmn" in nimf:
			pred_name += "cmn_"

		# which cell ??
		pred_name += args.test_cell

		pred_name += ".txt"
		# ___


		pred_path = os.path.join(
			os.path.dirname(__file__), outdir, "prediction", model_name, pred_name
		)
		os.makedirs(os.path.dirname(pred_path), exist_ok=True)

		test(
			model_class=model_class, 
			model_params=config["model_opts"],
			optimizer_class=torch.optim.Adam, 
			optimizer_params=optimizer_params,
			dataset=all_test_data,
			groups=all_test_data.metainfo["chrom"],
			test_chroms=chrom_split[f"fold{k}"]["test_chroms"],
			batch_size=config["train_opts"]["batch_size"], 
			num_workers=config["train_opts"]["num_workers"],
			outpath=pred_path,
			model_path=os.path.join(os.path.dirname(__file__), outdir, "model", model_name, f"best_epoch.pt")
		)
