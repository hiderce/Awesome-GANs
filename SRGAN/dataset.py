# will be changed to another DataSet, e.g ImageNet
# this is for temporary

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import os
import h5py
import numpy as np
from glob import glob
from tqdm import tqdm
from scipy.misc import imread, imresize

'''
This dataset is for Celeb-A

- Celeb-A
    Celeb-A DataSets can be downloaded at http://mmlab.ie.cuhk.edu.hk/projects/CelebA.html

    Celeb-A link : https://drive.google.com/drive/folders/0B7EVK8r0v71pTUZsaXdaSnZBZzg
        
    OR you can download following python code (but it doesn't work as well when i'm trying)
    code link : https://github.com/carpedm20/DCGAN-tensorflow/blob/master/download.py
'''

DataSets = {
    # Linux
    # 'celeb-a': '/home/zero/hdd/DataSet/Celeb-A/img_align_celeba',
    # 'celeb-a-h5': '/home/zero/hdd/DataSet/Celeb-A/celeb-a.h5',
    # Windows
    'celeb-a': 'D:\\DataSet\\Celeb-A\\img_align_celeba\\',
    'celeb-a-h5': 'D:\\DataSet\\Celeb-A\\celeb-a.h5',
}


class CelebADataSet:

    def __init__(self, batch_size=128, input_height=32, input_width=32, input_channel=3,
                 output_height=32, output_width=32, output_channel=3,
                 split_rate=0.2, random_state=42, num_threads=8, mode='w'):

        """
        # General Settings
        :param batch_size: training batch size, default 128
        :param input_height: input image height, default 32
        :param input_width: input image width, default 32
        :param input_channel: input image channel, default 3 (RGB)
        - in case of Celeb-A, image size is 32x32x3(HWC).

        # Output Settings
        :param output_height: output images height, default 32
        :param output_width: output images width, default 32
        :param output_channel: output images channel, default 3

        # Pre-Processing Option
        :param split_rate: image split rate (into train & test), default 0.2
        :param random_state: random seed for shuffling, default 42
        :param num_threads: the number of threads for multi-threading, default 8

        # DataSet Option
        :param mode: file mode(RW), default w
        """

        self.batch_size = batch_size
        self.input_height = input_height
        self.input_width = input_width
        self.input_channel = input_channel
        self.image_shape = [self.batch_size, self.input_height, self.input_width, self.input_channel]

        self.output_height = output_height
        self.output_width = output_width
        self.output_channel = output_channel

        self.split_rate = split_rate
        self.random_state = random_state
        self.num_threads = num_threads  # change this value to the fitted value for ur system
        self.mode = mode

        self.path = ""      # DataSet path
        self.files = ""     # files' name
        self.n_classes = 0  # DataSet the number of classes, default 10

        self.data = []      # loaded images
        self.num_images = 202599
        self.images = []

        self.celeb_a(mode=self.mode)  # load Celeb-A

    def celeb_a(self, mode):
        def get_image(path, w, h):
            img = imread(path).astype(np.float)

            orig_h, orig_w = img.shape[:2]
            new_h = int(orig_h * w / orig_w)

            img = imresize(img, (new_h, w))
            margin = int(round((new_h - h) / 2))

            return img[margin:margin + h]

        if mode == 'w':
            self.files = glob(os.path.join(DataSets['celeb-a'], "*.jpg"))
            self.files = np.sort(self.files)

            self.data = np.zeros((len(self.files), self.input_height * self.input_width * self.input_channel),
                                 dtype=np.uint8)

            print("[*] Image size : ", self.data.shape)

            assert (len(self.files) == self.num_images)

            for n, f_name in tqdm(enumerate(self.files)):
                image = get_image(f_name, self.input_width, self.input_height)
                self.data[n] = image.flatten()

            # write .h5 file for reusing later...
            with h5py.File(''.join([DataSets['celeb-a-h5']]), 'w') as f:
                f.create_dataset("images", data=self.data)

        self.images = self.load_data(size=self.num_images)

    def load_data(self, size, offset=0):
        """
            From great jupyter notebook by Tim Sainburg:
            http://github.com/timsainb/Tensorflow-MultiGPU-VAE-GAN
        """
        with h5py.File(DataSets['celeb-a-h5'], 'r') as hf:
            faces = hf['images']

            full_size = len(faces)
            if size is None:
                size = full_size

            n_chunks = int(np.ceil(full_size / size))
            if offset >= n_chunks:
                print("[*] Looping from back to start.")
                offset = offset % n_chunks

            if offset == n_chunks - 1:
                print("[-] Not enough data available, clipping to end.")
                faces = faces[offset * size:]

            else:
                faces = faces[offset * size:(offset + 1) * size]

            faces = np.array(faces, dtype=np.float16)

        print("[+] Image size : ", faces.shape)

        return faces / 255.


class DataIterator:

    def __init__(self, x, y, batch_size, label_off=False):
        self.x = x
        self.label_off = label_off
        if not label_off:
            self.y = y
        self.batch_size = batch_size
        self.num_examples = num_examples = x.shape[0]
        self.num_batches = num_examples // batch_size
        self.pointer = 0

        assert self.batch_size <= self.num_examples

    def next_batch(self):
        start = self.pointer
        self.pointer += self.batch_size

        if self.pointer > self.num_examples:
            perm = np.arange(self.num_examples)
            np.random.shuffle(perm)

            self.x = self.x[perm]
            if not self.label_off:
                self.y = self.y[perm]

            start = 0
            self.pointer = self.batch_size

        end = self.pointer

        if not self.label_off:
            return self.x[start:end], self.y[start:end]
        else:
            return self.x[start:end]

    def iterate(self):
        for step in range(self.num_batches):
            yield self.next_batch()