from multiprocessing import shared_memory
import numpy as np

segment_name = "segment"
data_shape = (5,5,5)


def get_view(shm):
    shape = (1,) + data_shape
    arr_one = np.ndarray(shape, dtype=np.float64, buffer=shm.buf)
    arr_two = np.ndarray(data_shape, dtype=np.float64, buffer=arr_one[0])
    return arr_two


def f1():
    arr = get_view(shared_memory.SharedMemory(name=segment_name))
    print(arr[0][0][0])


def f2():
    shm = shared_memory.SharedMemory(name=segment_name)
    arr = get_view(shm)
    print(arr[0][0][0])


if __name__ == '__main__':
    shape = (1,) + data_shape
    dummy = np.ndarray(shape, dtype=np.float64)
    shared_memory.SharedMemory(name=segment_name, create=True, size=dummy.nbytes)
    f2()
    f1()


