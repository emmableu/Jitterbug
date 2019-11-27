from __future__ import print_function, division
import pickle
from pdb import set_trace
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import csv
from collections import Counter
from sklearn import svm
from sklearn import tree
import matplotlib.pyplot as plt
import time
import os
from sklearn import preprocessing
import pandas as pd
from scipy.spatial import distance
from sklearn.naive_bayes import MultinomialNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier


class Transfer(object):
    def __init__(self):
        self.fea_num = 4000
        self.step = 10
        self.enough = 30
        self.kept=50
        self.atleast=100
        self.enable_est = True
        self.interval = 500000000
        self.ham=False
        self.seed = 0





    def create(self,data,target):
        self.flag=True
        self.hasLabel=True
        self.record={"x":[],"pos":[],'est':[]}
        self.body={}
        self.est=[]
        self.last_pos=0
        self.last_neg=0
        self.record_est={"x":[],"semi":[],"sigmoid":[]}
        self.record_time = {"x":[],"pos":[]}
        self.round = 0
        self.est_num = 0

        self.target = target
        self.loadfile(data[target])

        self.create_old(data)
        self.preprocess()

        return self



    def loadfile(self,data):
        self.body = data
        self.body['code']=["undetermined"]*len(self.body)
        self.body['fixed']=[0]*len(self.body)
        self.body['count']=[0]*len(self.body)
        self.body['time']=[0.0]*len(self.body)
        # self.start_time = np.min(self.body['time'])
        self.newpart = len(self.body)
        return

    ### Use previous knowledge, labeled only
    def create_old(self,data):
        bodies = [self.body]
        for key in data:
            if key == self.target:
                continue
            body = data[key]
            label = body["label"]
            body['code']=pd.Series(label)
            body['fixed']=pd.Series([1]*len(label))
            body['count']=pd.Series([0]*len(label))
            bodies.append(body)

        self.body = pd.concat(bodies,ignore_index = True)




    def get_numbers(self):
        total = len(self.body["code"][:self.newpart])
        pos = Counter(self.body["code"][:self.newpart])["yes"]
        neg = Counter(self.body["code"][:self.newpart])["no"]


        try:
            tmp=self.record['x'][-1]
        except:
            tmp=-1
        if int(pos+neg)>tmp:
            self.record['x'].append(int(pos+neg))
            self.record['pos'].append(int(pos))
            self.record['est'].append(int(self.est_num))
        self.pool = np.where(np.array(self.body['code'][:self.newpart]) == "undetermined")[0]
        self.labeled = list(set(range(len(self.body['code'][:self.newpart]))) - set(self.pool))
        return pos, neg, total


    def preprocess(self):
        content = [c.decode("utf8","ignore") for c in self.body["Abstract"]]

        tfer = TfidfVectorizer(lowercase=True, analyzer="word", norm=None, use_idf=False, smooth_idf=False,sublinear_tf=False,decode_error="ignore")
        self.csr_mat = tfer.fit_transform(content)
        self.voc = tfer.vocabulary_.keys()



        #######################################################

        ### Feature selection by tfidf in order to keep vocabulary ###
        # tfidfer = TfidfVectorizer(lowercase=True, stop_words="english", norm=None, use_idf=True, smooth_idf=False,
        #                         sublinear_tf=False,decode_error="ignore",max_features=4000)
        # tfidfer.fit(content)
        # self.voc = tfidfer.vocabulary_.keys()
        #
        #
        #
        #
        # ##############################################################
        #
        # ### Term frequency as feature, L2 normalization ##########
        # tfer = TfidfVectorizer(lowercase=True, stop_words="english", norm=u'l2', use_idf=False,
        #                 vocabulary=self.voc,decode_error="ignore")
        # # tfer = TfidfVectorizer(lowercase=True, stop_words="english", norm=None, use_idf=False,
        # #                 vocabulary=self.voc,decode_error="ignore")
        # self.csr_mat=tfer.fit_transform(content)
        ########################################################
        return

    ## Train model ##
    def train(self,pne=False,weighting=True):

        # clf = svm.SVC(kernel='linear', probability=True, class_weight='balanced') if weighting else svm.SVC(kernel='linear', probability=True)
        clf = RandomForestClassifier(class_weight='balanced')
        clf_pre = tree.DecisionTreeClassifier(class_weight='balanced')
        poses = np.where(np.array(self.body['code']) == "yes")[0]
        negs = np.where(np.array(self.body['code']) == "no")[0]
        left = poses
        decayed = list(left) + list(negs)
        unlabeled = self.pool
        try:
            unlabeled = np.random.choice(unlabeled,size=np.max((len(decayed),2*len(left),self.atleast)),replace=False)
        except:
            pass

        if not pne:
            unlabeled=[]

        labels=np.array([x if x!='undetermined' else 'no' for x in self.body['code']])
        all_neg=list(negs)+list(unlabeled)
        sample = list(decayed) + list(unlabeled)

        clf_pre.fit(self.csr_mat[sample], labels[sample])


        ## aggressive undersampling ##
        if len(poses)>=self.enough:
            pos_at = list(clf_pre.classes_).index("yes")
            train_dist = clf_pre.predict_proba(self.csr_mat[all_neg])[:,pos_at]
            negs_sel = np.argsort(train_dist)[:len(left)]
            sample = list(left) + list(np.array(all_neg)[negs_sel])

        elif pne:
            pos_at = list(clf_pre.classes_).index("yes")
            train_dist = clf_pre.predict_proba(self.csr_mat[unlabeled])[:,pos_at]
            unlabel_sel = np.argsort(train_dist)[:int(len(unlabeled) / 2)]
            sample = list(decayed) + list(np.array(unlabeled)[unlabel_sel])
        clf.fit(self.csr_mat[sample], labels[sample])



        uncertain_id, uncertain_prob = self.uncertain(clf)
        certain_id, certain_prob = self.certain(clf)

        return uncertain_id, uncertain_prob, certain_id, certain_prob

        ## Get uncertain ##
    def uncertain(self,clf):
        pos_at = list(clf.classes_).index("yes")
        prob = clf.predict_proba(self.csr_mat[self.pool])[:, pos_at]
        # train_dist = clf.decision_function(self.csr_mat[self.pool])
        # order = np.argsort(np.abs(train_dist))[:self.step]  ## uncertainty sampling by distance to decision plane
        order = np.argsort(np.abs(prob-0.5))   ## uncertainty sampling by prediction probability
        return np.array(self.pool)[order], np.array(prob)[order]

    ## Get certain ##
    def certain(self,clf):
        pos_at = list(clf.classes_).index("yes")
        prob = clf.predict_proba(self.csr_mat[self.pool])[:,pos_at]
        order = np.argsort(prob)[::-1]
        return np.array(self.pool)[order],np.array(self.pool)[order]


    ## Get random ##
    def random(self):
        return np.random.choice(self.pool,size=np.min((self.step,len(self.pool))),replace=False)

    ## Get one random ##
    def one_rand(self):
        pool_yes = filter(lambda x: self.body['label'][x]=='yes', range(len(self.body['label'])))
        return np.random.choice(pool_yes, size=1, replace=False)

    ## Format ##
    def format(self,id,prob=[]):
        result=[]
        for ind,i in enumerate(id):
            tmp = {key: self.body[key][i] for key in self.body}
            tmp["id"]=str(i)
            if prob!=[]:
                tmp["prob"]=prob[ind]
            result.append(tmp)
        return result



    ## Code candidate studies ##
    def code(self,id,label):

        self.body["code"][id] = label
        self.body["time"][id] = time.time()


    def code_batch(self,ids):
        now = time.time()
        times = [now+id/10000000.0 for id in range(len(ids))]
        labels = self.body["label"][ids]
        self.body["code"][ids] = labels
        self.body["time"][ids] =times




    def APFD(self):
        order = np.argsort(self.body["time"][:self.newpart])
        labels = self.body["code"][order]
        n = self.newpart
        m = Counter(self.body["label"][:self.newpart])["yes"]
        apfd = 0
        for i,label in enumerate(labels):
            if label == 'yes':
                apfd += (i+1)
        apfd = 1-float(apfd)/n/m+1/(2*n)
        return apfd

    def get_allpos(self):
        return len([1 for c in self.body["label"][:self.newpart] if c=="yes"])-self.last_pos

