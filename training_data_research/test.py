import pandas as pd 
import numpy as np

def test_pandas():
    df = pd.DataFrame({
        "A": [1, 2, 3, 4, 5]
    })

    df = df[df["A"] != 1]
    print(df)

def test_numpy():
    a = np.arange(25).reshape(5, 5)
    print(a)

    print(a[:3, :2])
    
def test_list():
    l = [[1, 2], [1, 2], [1, 2]]
    l = [prob[1] for prob in l]
    print(l)


test_list()