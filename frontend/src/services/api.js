import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Email Services
export const emailService = {
  analyzeEmail: async (emailData) => {
    try {
      const response = await apiClient.post('/emails/analyze', emailData);
      return response.data;
    } catch (error) {
      throw error.response?.data || error.message;
    }
  },

  getEmailHistory: async (limit = 50, offset = 0, isPhishing = null) => {
    try {
      let url = `/emails/history?limit=${limit}&offset=${offset}`;
      if (isPhishing !== null) {
        url += `&is_phishing=${isPhishing}`;
      }
      const response = await apiClient.get(url);
      return response.data;
    } catch (error) {
      throw error.response?.data || error.message;
    }
  },

  getEmailDetails: async (emailId) => {
    try {
      const response = await apiClient.get(`/emails/${emailId}`);
      return response.data;
    } catch (error) {
      throw error.response?.data || error.message;
    }
  },

  getStatistics: async () => {
    try {
      const response = await apiClient.get('/emails/statistics');
      return response.data;
    } catch (error) {
      throw error.response?.data || error.message;
    }
  },

  getPhase2Metrics: async () => {
    try {
      const response = await apiClient.get('/emails/phase2-metrics');
      return response.data;
    } catch (error) {
      throw error.response?.data || error.message;
    }
  },

  markAsPhishing: async (emailId) => {
    try {
      const response = await apiClient.post(`/emails/${emailId}/mark-phishing`);
      return response.data;
    } catch (error) {
      throw error.response?.data || error.message;
    }
  },

  markAsSafe: async (emailId) => {
    try {
      const response = await apiClient.post(`/emails/${emailId}/mark-safe`);
      return response.data;
    } catch (error) {
      throw error.response?.data || error.message;
    }
  },
};

export default apiClient;
