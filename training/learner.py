'''
Stuff I want to do here:
 - Receive samples of data points
   - Each batch will go into a queue
   - If the queue is long enough, evict the current batch immediately
 - Train a model, continuously
   - Shuffle the current batch and go through it once
 - Periodically checkpoint the model
   - Save to disk somewhere, timestamped
   - Update the h5 group
 - Evaluate each model checkpoint against the current model used for self-play
    - If necessary, update the self-play model
'''
import attr
import h5py
import logging
import os
import numpy as np
import random
from multiprocessing import Queue

from tensorflow.keras.models import load_model

from training import model, constants as model_const

MODEL_FILE_NAME = "model.h5"


@attr.s
class Learner:
    model_base_path = attr.ib()
    model = attr.ib()
    training_queue = attr.ib()
    current_data = attr.ib(factory=list)

    @classmethod
    def from_file(cls, model_base_path, training_queue):
        model_file = os.path.join(model_base_path, MODEL_FILE_NAME)
        if os.path.exists(model_file):
            network = load_model(model_file)
        else:
            network = model.network()
            network.compile(optimizer='SGD', loss='categorical_crossentropy')
        return cls(model_base_path, network, training_queue)

    def start(self):
        while True:
            boards, data = [], []
            ys = [[] for _ in range(len(model_const.Head))]
            logging.debug('Waiting for samples')
            print('Learner waiting for samples')
            b, d, y = self.training_queue.get()
            boards.append(b)
            data.append(d)
            for i, h in enumerate(y):
                ys[i].append(h)

            logging.debug('Emptying queue')
            print('Learner emptying queue')
            while not self.training_queue.empty():
                b, d, y = self.training_queue.get()
                boards.append(b)
                data.append(d)
                for i, h in enumerate(y):
                    ys[i].append(h)
            boards_np = np.vstack(boards)
            data_np = np.vstack(data)
            y = [np.vstack(h) for h in ys]
            print(f'Learner training on {len(boards_np)} samples')
            logging.debug(f'Training on {len(boards_np)} samples')
            self.model.fit([boards_np, data_np], y, epochs=1, verbose=1)
