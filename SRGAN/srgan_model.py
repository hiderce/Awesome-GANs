import tensorflow as tf


tf.set_random_seed(777)  # reproducibility


def conv2d(x, f=64, k=3, d=1, act=None, pad='SAME', name='conv2d'):
    """
    :param x: input
    :param f: filters, default 64
    :param k: kernel size, default 3
    :param d: strides, default 2
    :param act: activation function, default None
    :param pad: padding (valid or same), default same
    :param name: scope name, default conv2d
    :return: covn2d net
    """
    return tf.layers.conv2d(x,
                            filters=f, kernel_size=k, strides=d,
                            kernel_initializer=tf.contrib.layers.variance_scaling_initializer(),
                            kernel_regularizer=tf.contrib.layers.l2_regularizer(5e-4),
                            bias_initializer=tf.zeros_initializer(),
                            activation=act,
                            padding=pad, name=name)


def batch_norm(x, momentum=0.9, eps=1e-9):
    return tf.layers.batch_normalization(inputs=x,
                                         momentum=momentum,
                                         epsilon=eps,
                                         scale=True,
                                         training=True)


class SRGAN:

    def __init__(self, s, batch_size=16, input_height=32, input_width=32, input_channel=3,
                 sample_num=1, sample_size=64, output_height=64, output_width=64,
                 df_dim=64, gf_dim=64,
                 z_dim=128, g_lr=1e-4, d_lr=1e-4):

        """
        # General Settings
        :param s: TF Session
        :param batch_size: training batch size, default 16
        :param input_height: input image height, default 32
        :param input_width: input image width, default 32
        :param input_channel: input image channel, default 3 (RGB)
        - in case of Celeb-A, image size is 32x32x3(HWC).

        # Output Settings
        :param sample_num: the number of output images, default 1
        :param sample_size: sample image size, default 64
        :param output_height: output images height, default 64
        :param output_width: output images width, default 64

        # For CNN model
        :param df_dim: discriminator filter, default 64
        :param gf_dim: generator filter, default 64

        # Training Option
        :param z_dim: z dimension (kinda noise), default 128
        :param g_lr: generator learning rate, default 1e-4
        :param d_lr: discriminator learning rate, default 1e-4
        """

        self.s = s
        self.batch_size = batch_size

        self.input_height = input_height
        self.input_width = input_width
        self.input_channel = input_channel
        self.image_shape = [-1, self.input_height, self.input_width, self.input_channel]

        self.sample_num = sample_num
        self.sample_size = sample_size
        self.output_height = output_height
        self.output_width = output_width

        self.df_dim = df_dim
        self.gf_dim = gf_dim

        self.z_dim = z_dim
        self.beta1 = 0.9
        self.beta2 = 0.999
        self.d_lr = d_lr
        self.g_lr = g_lr
        self.lr_decay_rate = 0.5
        self.lr_low_boundary = 1e-5

        # LR update
        self.d_lr_update = tf.assign(self.d_lr, tf.maximum(self.d_lr * self.lr_decay_rate, self.lr_low_boundary))
        self.g_lr_update = tf.assign(self.g_lr, tf.maximum(self.g_lr * self.lr_decay_rate, self.lr_low_boundary))

        # pre-defined
        self.d_real = 0
        self.d_fake = 0
        self.d_loss = 0.
        self.g_loss = 0.

        self.d_op = None
        self.g_op = None
        self.merged = None
        self.writer = None
        self.saver = None

        # Placeholders
        self.x = tf.placeholder(tf.float32, shape=self.image_shape, name="x-image")  # (-1, 64, 64, 3)
        self.z = tf.placeholder(tf.float32, shape=[-1, self.z_dim], name='z-noise')  # (-1, 128)

        self.build_began()  # build BEGAN model

    def discriminator(self, x, reuse=None):
        """
        :param x: images (-1, 32, 32, 3)
        :param reuse: re-usability
        :return: prob
        """
        with tf.variable_scope("discriminator", reuse=reuse):
            x = conv2d(x, self.df_dim, act=tf.nn.leaky_relu, name='d-conv2d-0')

            filters = [1, 2, 2, 4, 4, 8, 8]
            filters = list(map(lambda fs: fs * self.df_dim, filters))

            for i, f in enumerate(filters):
                x = conv2d(x, f=f, k=3, d=i % 2, act=tf.nn.leaky_relu, name='d-conv2d-%d' % (i + 1))
                x = batch_norm(x)

            # x : (-1, 4, 4, 8 * 64)
            x = tf.layers.flatten(x)  # (-1, 4 * 4 * 8 * 64)

            x = tf.layers.dense(x, 1024, activation=tf.nn.leaky_relu, name='d-fc-0')
            x = tf.layers.dense(x, 1, activation=tf.nn.sigmoid, name='d-fc-1')

            return x

    def generator(self, z, reuse=None):
        """
        :param z: embeddings
        :param reuse: re-usable
        :return: logits
        """
        with tf.variable_scope("generator", reuse=reuse):
            # z : (batch_size, 128)

            return z

    def build_began(self):
        def mse_loss(pred, data):
            return tf.sqrt(2 * tf.nn.l2_loss(pred - data)) / self.batch_size

        # Generator
        self.g = self.generator(self.z)

        # Discriminator
        d_real = self.discriminator(self.x)
        d_fake = self.discriminator(self.g, reuse=True)

        # Following LSGAN Loss
        d_real_loss = tf.reduce_sum(mse_loss(d_real, tf.ones_like(d_real)))
        d_fake_loss = tf.reduce_sum(mse_loss(d_fake, tf.zeros_like(d_fake)))
        self.d_loss = (d_real_loss + d_fake_loss) / 2.
        self.g_loss = tf.reduce_sum(mse_loss(d_fake, tf.ones_like(d_fake)))

        # Summary
        tf.summary.histogram("z-noise", self.z)

        tf.summary.image("g", self.g)  # generated images by Generative Model
        tf.summary.scalar("d_loss", self.d_loss)
        tf.summary.scalar("d_real_loss", d_real_loss)
        tf.summary.scalar("d_fake_loss", d_fake_loss)
        tf.summary.scalar("g_loss", self.g_loss)

        # Optimizer
        t_vars = tf.trainable_variables()
        d_params = [v for v in t_vars if v.name.startswith('d')]
        g_params = [v for v in t_vars if v.name.startswith('g')]

        self.d_op = tf.train.AdamOptimizer(learning_rate=self.d_lr,
                                           beta1=self.beta1, beta2=self.beta2).minimize(self.d_loss, var_list=d_params)
        self.g_op = tf.train.AdamOptimizer(learning_rate=self.g_lr,
                                           beta1=self.beta1, beta2=self.beta2).minimize(self.g_loss, var_list=g_params)

        # Merge summary
        self.merged = tf.summary.merge_all()

        # Model saver
        self.saver = tf.train.Saver(max_to_keep=1)
        self.writer = tf.summary.FileWriter('./model/', self.s.graph)