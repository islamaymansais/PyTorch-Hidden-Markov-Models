import utils
import numpy as np

from itertools import chain 
from collections import Counter

class BaumWelch():

    def __init__(self, obs_seq, hid_seq):

        self._epsilon = 0.0001
        self._iterations = len(obs_seq)

        self._obs_seq = obs_seq
        self._hid_seq = hid_seq

        self._num_obs = len(set(obs_seq))
        self._num_hids = len(set(hid_seq))

        self._pi_shape = [1, self._num_hids]
        self._pi = torch.zeros(size = self._pi_shape, dtype = torch.float64)

        self._emiss_shape = [self._num_hids, self._num_obs]
        self._emission = torch.zeros(size = self._emiss_shape, dtype = torch.float64)

        self._A_shape = [self._num_hids, self._num_hids]
        self._A = torch.zeros(size = self.trans_shape, dtype = torch.float64)

        self._Alpha_beta_shape = [self._num_hids, len(self.obs_seq)]
        self._Alpha = torch.zeros(size = self._Alpha_beta_shape, dtype = torch.float64)
        self._beta = torch.zeros(size = self._Alpha_beta_shape, dtype = torch.float64)

    def _expected_output_occurrence(self, index, step_gammas, summed_gammas):
        filtered_gamma = step_gammas.index_select(1, torch.LongTensor(index))
        sum_filtered_gamma = filtered_gamma.sum(dim = 1)
        new_obs_prob = torch.div(sum_filtered_gamma, summed_gammas)
        return new_obs_prob
    
    def _forward(self):  
        alpha_initial = self._pi * self._emission[:, self.obs_seq[0]]
        self._Alpha[:, 0] = torch.div(alpha_initial, alpha_initial.sum())
        for i, obs in enumerate(self.obs_seq[1:]):
            current_probability = torch.matmul(self._Alpha[:, i], A)
            forward_probability = torch.mul(current_probability, self._emission[:, obs])
            self._Alpha[:, i+1] = torch.div(forward_probability, forward_probability.sum())

    def _backward(self):  
        self._beta[:, -1] = torch.from_numpy(np.array([1.0, 1.0]))
        for i, obs in enumerate(self.obs_seq[:0:-1]):
            x = torch.mul(self._emission[:, obs], self._A)
            beta = torch.matmul(x, self._beta[:, -(i+1)])
            self._beta[:, -(i+2)] = torch.div(beta, beta.sum())

    def _calculate_gammas(self):
        num = torch.mul(self._Alpha, self._beta)
        denom = torch.sum(num, dim = 0)
        gamma_i = torch.div(num, denom)
        return gamma_i

    def _calculate_zetas(self):
        zetas = []
        A_T = torch.transpose(self._A, 1, 0)
        for t, fwd in enumerate(self._Alpha[:, :-1].transpose(1, 0)):
            x = torch.mul(fwd, A_T)
            numerator = torch.transpose(x, 1, 0) * self._emission[:, self.obs_seq[t+1]] * self._beta[:, t+1]
            denomenator = torch.sum(numerator, dim = 0).sum(dim = 0)
            zeta = torch.div(numerator, denomenator)
            zetas.append(zeta)
        summed_zetas = torch.stack(zetas, dim = 0).sum(dim = 0)
        return summed_zetas

    def _re_estimate_parameters(self):

        step_gammas = self._calculate_gammas()

        ##################################################
        #       Re-estimate initial probabilities
        ##################################################

        new_pi = step_gammas[:, 0]

        ##################################################
        #         Re-estimate transition matrix
        ##################################################

        summed_zetas = self._calculate_zetas()
        summed_gammas = torch.sum(step_gammas[:, :-1], dim = 1)
        new_transition_matrix = torch.div(summed_zetas, summed_gammas.view(-1, 1))

        ##################################################
        #         Re-estimate emission matrix
        ##################################################

        summed_gammas = torch.sum(step_gammas, dim = 1)
        state_indices = [np.where(self._obs_seq == searchval)[0] for searchval in set(self.obs_seq)]
        new_emission_matrix = [self._expected_output_occurrence(value, step_gammas, summed_gammas) for value in state_indices]   
        new_emission_matrix = torch.stack(new_emission_matrix, dim = 0).transpose(1, 0)

        return new_pi, new_transition_matrix, new_emission_matrix

    def check_convergence(self, new_pi, new_transition_matrix, new_emission_matrix):
        delta_pi = torch.max(torch.abs(self._pi - new_pi)).item() < self._epsilon
        delta_transition_mat = torch.max(torch.abs(self._A - new_transition_matrix)).item() < self._epsilon
        delta_emission_mat = torch.max(torch.abs(self._emission - new_emission_matrix)).item() < self._epsilon
        converged =  [delta_pi, delta_transition_mat, delta_emission_mat]
        if not all(converged):
            return False
        else:
            return True

    def _expectation_maximization(self):
        # Expectation
        self._forward()
        self._backward()

        # Maximization 
        new_pi, new_transition_matrix, new_emission_matrix = self._re_estimate_parameters()

        converged = self.check_convergence(new_pi, new_transition_matrix, new_emission_matrix)

        self._pi = new_pi
        self._A = new_transition_matrix
        self._emission = new_emission_matrix

        return converged

    def baum_welch_algo(self):

        for i in range(self._iterations):
            converged = self._expectation_maximization()
            if converged:
                print("Converged at iteration: {}".format(i))
                break
                
        return self._pi, self._A, self._emission

if __name__ == "__main__":

    bm = BaumWelch()