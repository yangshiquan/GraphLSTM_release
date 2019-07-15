#!/bin/bash

LOCAL_HOME=/Users/shiquan/PycharmProjects/GraphLSTM_release  # where the theano_src directory reside

cd ${LOCAL_HOME}

DATA_DIR=${LOCAL_HOME}/data # The data directory
PP_DIR=${LOCAL_HOME}/results/Nary_param_and_predictions # The directory for the prediction files
OUT_DIR=${LOCAL_HOME}/results/Nary_results  # The log output dirctory

THEANO_FLAGS=mode=FAST_RUN,device=$3,floatX=float32,nvcc.flags=-use_fast_math,exception_verbosity=high time python theano_src/lstm_RE.py --setting run_single_corpus --data_dir ${DATA_DIR}/drug_var/ --emb_dir ${DATA_DIR}/glove/glove.6B.100d.txt --total_fold 5 --dev_fold $1 --test_fold $1 --num_entity 2 --circuit $2 --batch_size 8 --lr 0.02 --lstm_type_dim 2 --content_file sentences_2nd --dependent_file graph_arcs --parameters_file ${PP_DIR}/all_drug_var_best_params_$2.cv$1.lr0.02.bt8 --prediction_file ${PP_DIR}/all_drug_var_$2.cv$1.predictions > ${OUT_DIR}/all_drug_var.accuracy.$2.cv$1.lr0.02.bt8.noName
