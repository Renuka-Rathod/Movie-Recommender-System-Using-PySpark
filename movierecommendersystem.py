# -*- coding: utf-8 -*-
"""MovieRecommenderSystem.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1FT6ZA1ZeSvWqEk1oWfIUN3-ADEox1tvS
"""

!pip install pyspark

"""#Step 1: Creating a PySpark Session

"""

# import the required libraries
import time
import pyspark
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName('recommendation').getOrCreate()

"""
#Step 2: Loading and Preprocessing Data"""

# load the datasets using pyspark
movies = spark.read.load("/content/movies.csv", format='csv', header = True)
ratings = spark.read.load('/content/ratings.csv', format='csv', header = True)
links = spark.read.load("/content/links.csv", format='csv', header = True)
tags = spark.read.load("/content/tags.csv", format='csv', header = True)
ratings.show()
movies.show()
links.show()
tags.show()

# print the schema to understand the data types of features
ratings = ratings.select("userId", "movieId", "rating")
ratings.printSchema()

# convert the data type to integer and float
df = ratings.withColumn('userId', ratings['userId'].cast('int')).\
withColumn('movieId', ratings['movieId'].cast('int')).withColumn('rating', ratings['rating'].cast('float'))
df.printSchema()

# split the data into train, validation and test sets
train, validation, test = df.randomSplit([0.6,0.2,0.2], seed = 0)
print("The number of ratings in each set: {}, {}, {}".format(train.count(), validation.count(), test.count()))

"""#Step 3: Model Training and Validation"""

from pyspark.sql.functions import col, sqrt
def RMSE(predictions):
    squared_diff = predictions.withColumn("squared_diff", pow(col("rating") - col("prediction"), 2))
    mse = squared_diff.selectExpr("mean(squared_diff) as mse").first().mse
    return mse ** 0.5

# implement the model using ALS algorithm and find the right hyperparameters using Grid Search
from pyspark.ml.recommendation import ALS

def GridSearch(train, valid, num_iterations, reg_param, n_factors):
    min_rmse = float('inf')
    best_n = -1
    best_reg = 0
    best_model = None
    # run Grid Search for all the parameter defined in the range in a loop
    for n in n_factors:
        for reg in reg_param:
            als = ALS(rank = n,
                      maxIter = num_iterations,
                      seed = 0,
                      regParam = reg,
                      userCol="userId",
                      itemCol="movieId",
                      ratingCol="rating",
                      coldStartStrategy="drop")
            model = als.fit(train)
            predictions = model.transform(valid)
            rmse = RMSE(predictions)
            print('{} latent factors and regularization = {}: validation RMSE is {}'.format(n, reg, rmse))
            # track the best model using RMSE
            if rmse < min_rmse:
                min_rmse = rmse
                best_n = n
                best_reg = reg
                best_model = model

    pred = best_model.transform(train)
    train_rmse = RMSE(pred)
    # best model and its metrics
    print('\nThe best model has {} latent factors and regularization = {}:'.format(best_n, best_reg))
    print('traning RMSE is {}; validation RMSE is {}'.format(train_rmse, min_rmse))
    return best_model

# build the model using different ranges for Grid Search
from pyspark.sql.functions import col, sqrt
num_iterations = 10
ranks = [6, 8, 10, 12]
reg_params = [0.05, 0.1, 0.2, 0.4, 0.8]

start_time = time.time()
final_model = GridSearch(train, validation, num_iterations, reg_params, ranks)
print('Total Runtime: {:.2f} seconds'.format(time.time() - start_time))

# test the accuracy of the model on test set using RMSE
pred_test = final_model.transform(test)
print('The testing RMSE is ' + str(RMSE(pred_test)))

"""#Step 4 : Testing the recommendations for a Single User"""

# test for a single user
single_user = test.filter(test['userId']==12).select(['movieId','userId'])
single_user.show()

# fetch the names of the movies
single_user.join(movies, single_user.movieId == movies.movieId, 'inner').show()

# verify the prediction rating for the user
reccomendations = final_model.transform(single_user)
reccomendations.orderBy('prediction',ascending=False).show()

# fetch the names of the movies
reccomendations.join(movies, reccomendations.movieId == movies.movieId, 'inner').show()

"""#Step 5: Providing the recommendations to the user"""

from pyspark.sql.functions import col, lit

# select a single user from the test set
user_id = 12
single_user_ratings = test.filter(test['userId'] == user_id).select(['movieId', 'userId', 'rating'])

# display the movies the user has liked
print("Movies liked by user with ID", user_id)
single_user_ratings.join(movies, 'movieId').select('movieId', 'title', 'rating').show()

# generate recommendations for the user
all_movies = df.select('movieId').distinct()
user_movies = single_user_ratings.select('movieId').distinct()
movies_to_recommend = all_movies.subtract(user_movies)

# predict ratings for movies the user has not rated yet
recommendations = final_model.transform(movies_to_recommend.withColumn('userId', lit(user_id)))

# filter out the movies that the user has already rated or seen (this filters out the movies that the user has not liked as well)
recommendations = recommendations.filter(col('prediction') > 0)

# display the recommendations with movie names
print("Recommended movies for user with ID", user_id)
recommended_movies = recommendations.join(movies, 'movieId').select('movieId', 'title', 'prediction')

# Sort recommended movies by prediction in descending order
ordered_recommendations = recommended_movies.orderBy(col('prediction').desc())

# Display the ordered recommendations
ordered_recommendations.show()







