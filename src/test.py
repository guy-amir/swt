import random_forest_tf as rf
import numpy as np
from sklearn import datasets

digits = datasets.load_digits()

X, y = digits.images, digits.target

x = X.reshape(-1,64)

wf = rf.WaveletsForestRegressor()

wf.fit(x,y)

predictions = wf.predict(x)

print(f"predictions: {predictions}")

wf.evaluate_smoothness()