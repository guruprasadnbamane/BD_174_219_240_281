from pyspark.sql import SparkSession
from pyspark import SparkContext
from pyspark.sql.types import * 
from pyspark.streaming import StreamingContext
from pyspark.sql.functions import *
from sklearn.metrics import r2_score,accuracy_score, precision_score, recall_score
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.linalg import Vector
from pyspark.ml.pipeline import PipelineModel
from sklearn.linear_model import SGDClassifier
from pyspark.ml.feature import StopWordsRemover, Word2Vec, RegexTokenizer,StringIndexer
from sklearn.linear_model import PassiveAggressiveClassifier
from pyspark.ml import Pipeline
import joblib
import numpy as np
import csv
import pyspark.sql.functions as F
import re

flag = 0 
model_flag = 0
max_f1score = 0

def csv_writer(accuracy , fscore , precision, recall , score , max_f1score , file_path):
    
    global flag
    f_name = file_path+".csv"
    
    if flag == 0 :
        flag =1
        with open(f_name,'a') as c:
            cwriter_obj = csv.writer(c)
            cwriter_obj.writerow(["accuracy" , "fscore" , "precision" , "recall" , "score" , "max_f1score" ])
    
    #creating data row
    row = [accuracy , fscore , precision, recall , score , max_f1score]
    
    with open(f_name, 'a') as c:
            cwriter_obj = csv.writer(c)
            cwriter_obj.writerow(row)



def remove_pattern(input_txt, pattern):
    print(type(input_txt[0]))
    r = re.findall(pattern,str(input_txt))
   
    for i in r:
        input_txt = re.sub(i, '', input_txt)
        
    return input_txt        


def data_preprocessing(tup,sc):
    spark = SparkSession(sc)#-----------
    
    df = spark.createDataFrame(tup,schema=['tweet','Sentiment'])
    
    df = (df.withColumn("tweet", F.regexp_replace("tweet", r"[@#&][A-Za-z0-9-]+", "")))
    #df['tidy_tweet'] = np.vectorize(remove_pattern)(df['tweet'], "@[\w]*")
    #df.withColumn('tweet',np.vectorize(remove_pattern)(df['tweet'], "@[\w]*"))

    
    stage_2 = RegexTokenizer(inputCol= 'tweet' , outputCol= 'tokens', pattern= '\\W')
    # define stage 2: remove the stop words
    stopwordList = ['m']
    stage_3 = StopWordsRemover(inputCol= 'tokens', outputCol= 'filtered_words',stopWords=stopwordList)
    # define stage 3: create a word vector of the size 100
    stage_4 = Word2Vec(inputCol= 'filtered_words', outputCol= 'vector', vectorSize=8000)
    
    stage_1 = StringIndexer(inputCol='Sentiment',outputCol='label')
    # applying the pre procesed pipeling model on the batches of data recieved
    pipe = Pipeline(stages=[stage_1,stage_2,stage_3,stage_4])
    
    cleaner = pipe.fit(df)
    
    clean_data = cleaner.transform(df)
    
    clean_data = clean_data.select(['label','tweet','filtered_words','vector'])
    
    # batch data is splitted into train and test (.75 and .25)
    (training,testing) = clean_data.randomSplit([0.75,0.25])
    
    Yaxis_train = np.array(training.select('label').collect())
    
    Xaxis_train = np.array(training.select('vector').collect())
    # data reshaping
    dim_samples, dim_x, dim_y = Xaxis_train.shape
    
    Xaxis_train = Xaxis_train.reshape((dim_samples,dim_x*dim_y))
    
    Xaxis_test = np.array(testing.select('vector').collect())
    
    yaxis_test = np.array(testing.select('label').collect())
    
    dim_samples, dim_x, dim_y = Xaxis_test.shape
    
    Xaxis_test = Xaxis_test.reshape((dim_samples,dim_x*dim_y))
    
    return (Xaxis_test,yaxis_test,Xaxis_train,Yaxis_train)
    
def passiAggrClass_model(tup,sc):
    Xaxis_test,Yaxis_test,Xaxis_train,Yaxis_train = data_preprocessing(tup,sc)
    global model_flag,max_f1score
    max_f1score_flag = 0
    
    try: 
        if model_flag == 0:
        
            model_flag = 1
            print("1st iteration of PassiveAggressive Model has began")
            model = PassiveAggressiveClassifier()
            model.partial_fit(Xaxis_train,Yaxis_train.ravel(),classes=np.unique(Yaxis_train))
            pred_batch = model.predict(Xaxis_test)
            joblib.dump(model, 'weights/PAC.pkl')
            
        else:
        
            max_f1score_flag=1
            print("Increamental learning of PAC Model has began")
            model_load = joblib.load('weights/PAC.pkl')
            model_load.partial_fit(Xaxis_train,Yaxis_train.ravel())
            pred_batch = model_load.predict(Xaxis_test)
            joblib.dump(model_load, 'weights/PAC.pkl')
            
        #metrics of model computed
        score = r2_score(Yaxis_test, pred_batch)
        accuracy = accuracy_score(Yaxis_test, pred_batch)
        precision = precision_score(Yaxis_test, pred_batch,zero_division=0)
        recall = recall_score(Yaxis_test, pred_batch)
        if precision == 0 or recall == 0:
            fscore = 0
        else:
            fscore = (2*recall*precision)/(recall+precision)   
        
        print("Accuracy:",accuracy*100,"%")
        print("Precision: ",precision)
        print("Recall:",recall)
        print("F1score:",fscore)
        print("R2 score:",score)
        
        if max_f1score < fscore:
            max_f1score = fscore
            if max_f1score_flag == 1:
                joblib.dump(model_load,'max_PAC.pkl')
            else :
                joblib.dump(model,'max_PAC.pkl')
        csv_writer(accuracy , fscore , precision, recall , score , max_f1score, 'PAC')
        print("\n iteration ended \n")
    except Exception as e:
        print("error occured",e)
