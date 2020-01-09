    def evaluate_smoothness(rf,m=1000):
        '''
        Evaluates smoothness for a maximum of M-terms

        :m: Maximum terms to use. Default is 1000.
        :return: Smothness index, n_wavelets, errors.
        '''
        n_wavelets = []
        errors = []
        step = 10
        power = 2

        paths, n_nodes_ptr = self.rf.decision_path(self.X)
        predictions = np.zeros(np.shape(self.y))
        for m_step in range(2, m, step):
            if m_step > len(self.norms):
                break
            predictions += self.predict(self.X, m_step, max(m_step - step, 0), paths=paths)
            error_norms = np.power(np.sum(np.power(self.y - predictions, power), 1), 1. / power)
            total_error = np.sum(np.square(error_norms), 0) / len(self.X)
            if m_step > 0 and total_error > 0:
                logging.info('Error for m=%s: %s' % (m_step - 1, total_error))
                n_wavelets.append(m_step - 1)
                errors.append(total_error)

        n_wavelets_log = np.log(np.reshape(n_wavelets, (-1, 1)))
        errors_log = np.log(np.reshape(errors, (-1, 1)))

        regr = linear_model.LinearRegression()
        regr.fit(n_wavelets_log, errors_log)
        alpha = np.abs(regr.coef_[0][0])
        logging.info('Smoothness index: %s' % alpha)

        return alpha, n_wavelets, errors