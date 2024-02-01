import numpy as np


def cluster(a: np.ndarray, n: int):
    aa = a.copy()
    aa.sort(axis=0)
    n = n-1
    split_idx = np.argpartition(np.diff(aa), -n)[-n:]
    split_idx.sort()
    return np.split(aa, split_idx+1)

if __name__=='__main__':
    a = np.array([1, 2, 3, 10, 0, 11, 12, 13, 15])
    print(cluster(a, 2))