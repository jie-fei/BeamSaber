import argparse

import numpy as np
from scipy.signal import wiener
from chainer import Variable
from chainer import cuda
from chainer import serializers
import webrtcvad

from chime_data import get_audio_nochime, get_audio_babble
from fgnt.beamforming import gev_wrapper_on_masks
from fgnt.signal_processing import audiowrite, stft, istft, audioread
from nn_models import BLSTMMaskEstimator, SimpleFWMaskEstimator

"""
PS: the array of noise and speech should have same dimension,
    otherwise the code will be error.
    Current DEBUG: numpy einsum
"""

parser = argparse.ArgumentParser(description='NN GEV beamforming')
parser.add_argument('model',
                    help='Trained model file')
parser.add_argument('model_type',
                    help='Type of model (BLSTM or FW)')
parser.add_argument('--gpu', '-g', default=-1, type=int,
                    help='GPU ID (negative value indicates CPU)')
parser.add_argument('exNum',
                    help='Experiment order')
args = parser.parse_args()

# Prepare model
if args.model_type == 'BLSTM':
    model = BLSTMMaskEstimator()
elif args.model_type == 'FW':
    model = SimpleFWMaskEstimator()
else:
    raise ValueError('Unknown model type. Possible are "BLSTM" and "FW"')

serializers.load_hdf5(args.model, model)
if args.gpu >= 0:
    cuda.get_device(args.gpu).use()
    model.to_gpu()
xp = np if args.gpu < 0 else cuda.cupy

t_io = 0
t_net = 0
t_beamform = 0


def single_noise():
    audio_data = get_audio_nochime('new_dataset/2m/2m_pub_new', ch_range=range(1, 9), fs=49000)
    # audio_data = get_audio_nochime('new_dataset/new_audio/AUDIO_RECORDING', ch_range=range(1, 9), fs=49000)
    noise_audio = audioread('new_dataset/babble.wav', sample_rate=16000)
    noise_data = get_audio_babble(noise_audio, audio_data, 9)
    print("Noise audio: ", noise_data.shape)
    context_samples = 0

    print("audio_data: ", audio_data.shape, "noise_data: ", noise_data.shape, end="\n")

    Y = stft(audio_data, time_dim=1).transpose((1, 0, 2))
    N = stft(noise_data, time_dim=1).transpose((1, 0, 2))
    print(audio_data.shape, type(audio_data))
    print("Y: ", len(Y), "N: ", len(N), end="\n")

    Y_var = Variable(np.abs(Y).astype(np.float32), True)
    N_var = Variable(np.abs(N).astype(np.float32), True)
    print("Y_var: ", Y_var.shape, "N_var: ", N_var.shape, end="\n")

    # mask estimation

    N_masks = model.calc_mask_noise(N_var)
    X_masks = model.calc_mask_speech(Y_var)
    print("calculate n_mask x_mask")
    N_masks.to_cpu()
    X_masks.to_cpu()

    N_mask = np.median(N_masks.data, axis=1)
    X_mask = np.median(X_masks.data, axis=1)
    print("N_mask: ", N_mask.shape, "X_mask: ", X_mask.shape, end="\n")
    Y_hat = gev_wrapper_on_masks(Y, N_mask)

    audiowrite(istft(Y_hat), "new_dataset_result/AUDIO_REC_old_model_babble.wav", 49000, True, True)

    print('Finished')


def single_normal():
    audio_data = get_audio_nochime('data/new_dataset/216m/2m_pub_new', ch_range=range(1, 9), fs=16000)
    # audio_data = get_audio_nochime('data/new_dataset/audio_re/audio_re', ch_range=range(1, 9), fs=16000)
    # audio_data = get_audio_nochime('new_dataset/1m2/1m2', ch_range=range(1, 5), fs=16000)
    noise_data = get_audio_nochime('data/new_dataset/blstm_noise/noise_124', ch_range=range(1, 9), fs=16000)
    # blstm_noise = audioread('/home/hipo/workspace/BeamSaber/result/noise/noise_124.wav', sample_rate=16000)
    context_samples = 0

    print("audio_data: ", audio_data.shape, end="\n")

    Y = stft(audio_data, time_dim=1).transpose((1, 0, 2))
    N = stft(noise_data, time_dim=1).transpose((1, 0, 2))
    # blstm_noise = stft(blstm_noise)
    Y_phase = np.divide(Y, abs(Y))
    print("Y: ", Y.shape, "Y_phase: ", Y_phase.shape, end="\n")

    Y_var = Variable(np.abs(Y).astype(np.float32), True)
    N_var = Variable(np.abs(N).astype(np.float32), True)
    # blstm_noise = Variable(np.abs(blstm_noise).astype(np.float32), True)
    print("Y_var: ", Y_var.shape, "N_var: ", N_var.shape, end="\n")

    # mask estimation
    N_masks, X_masks = model.calc_masks(Y_var)
    Noise_masks = model.calc_mask_noise(N_var)

    N_masks.to_cpu()
    X_masks.to_cpu()
    Noise_masks.to_cpu()

    N_mask = np.median(N_masks.data, axis=1)
    X_mask = np.median(X_masks.data, axis=1)

    Noise_mask = np.median(Noise_masks.data, axis=1)

    # signal = audioread('data/new_dataset/216m/2m_pub_new' + '.CH{}.wav'.format(ch), sample_rate=16000)
    # noise = audioread('data/new_dataset/gevnoise/gevnoise' + '.CH{}.wav'.format(ch), sample_rate=16000)
    # signal_ = stft(signal)
    # noise_ = stft(noise)
    #
    # signal_phase = np.divide(signal, abs(signal_))
    # noise_masks = model.calc_mask_noise(noise_)
    # noise_to = np.multiply(noise_masks.data, signal_)
    # noise_to = np.multiply(noise_to, signal_phase)
    # audiowrite(istft(noise_to)[context_samples:],
    #            "/home/hipo/workspace/BeamSaber/result/noise/noise_to_.CH{}.wav".format(ch), 16000, True, True)

    Noise = np.multiply(N_masks.data, Y)
    Noise = np.multiply(Noise, Y_phase)
    Y_phase_med = np.median(Y_phase, axis=1)
    print(Noise.shape)
    # for ch in range(0, 8):
    #     audiowrite(istft(Noise[:,ch,:])[context_samples:],
    #                "/home/hipo/workspace/BeamSaber/result/noise/2mnoise_.CH{}.wav".format(ch), 16000, True, True)
    Noise = np.median(Noise, axis=1)

    print("N_mask: ", N_mask.shape, "X_mask: ", X_mask.shape, "Y_phase: ", Y_phase.shape, end="\n")
    Y_hat = gev_wrapper_on_masks(Y, N_mask, X_mask)
    print(Y_hat.shape)
    print("Noise: ", Noise.shape)
    audiowrite(istft(Noise)[context_samples:],
               "/home/hipo/workspace/BeamSaber/result/noise/noise_{}.wav".format(args.exNum), 16000, True, True)
    audiowrite(istft(Y_hat)[context_samples:],
               "/home/hipo/workspace/BeamSaber/result/enhanced/{}.wav".format(args.exNum), 16000, True, True)
    # nc_wiener = wiener(Y_hat, noise=Noise)
    # # nc_wiener = np.multiply(nc_wiener, np.median(Y, axis=1))
    # nc_wiener = np.multiply(nc_wiener, Y_phase_med)
    # audiowrite(istft(nc_wiener)[context_samples:],
    #            "/home/hipo/workspace/BeamSaber/result/enhanced/NC{}.wav".format(args.exNum), 16000, True, True)

if __name__ == '__main__':
    single_normal()
    # single_noise()
