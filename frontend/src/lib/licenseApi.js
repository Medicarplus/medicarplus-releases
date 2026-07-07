import axios from "axios";

const API_ROOT = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LS_TOKEN = "caja.admin.token";

export const licenseApi = axios.create({
  baseURL: `${API_ROOT}/licenses`,
  timeout: 15000,
});

licenseApi.interceptors.request.use((config) => {
  const t = localStorage.getItem(LS_TOKEN);
  if (t) config.headers["X-Admin-Token"] = t;
  return config;
});

export const AdminTokenStore = {
  get: () => localStorage.getItem(LS_TOKEN) || "",
  set: (t) => localStorage.setItem(LS_TOKEN, t),
  clear: () => localStorage.removeItem(LS_TOKEN),
};

// -------- Admin endpoints --------
export const listLicenses = async () => (await licenseApi.get("")).data;
export const getLicense = async (installId) =>
  (await licenseApi.get(`/${installId}`)).data;
export const generateLicense = async (payload) =>
  (await licenseApi.post("/generate", payload)).data;
export const revokeLicense = async (installId, reason) =>
  (await licenseApi.post("/revoke", { install_id: installId, reason })).data;
export const resetHwid = async (installId) =>
  (await licenseApi.post(`/${installId}/reset-hwid`)).data;

export const listRequests = async () =>
  (await licenseApi.get("/requests")).data;
export const approveRequest = async (id, payload = {}) =>
  (await licenseApi.post(`/requests/${id}/approve`, payload)).data;
export const rejectRequest = async (id, reason) =>
  (await licenseApi.post(`/requests/${id}/reject`, { reason })).data;

// -------- Public endpoints --------
export const createLicenseRequest = async (payload) =>
  (await axios.post(`${API_ROOT}/licenses/requests`, payload)).data;

export const pingAdmin = async (token) => {
  // Verifica un token intentant llistar (autoritzat = 200, sinó 401)
  const r = await axios.get(`${API_ROOT}/licenses`, {
    headers: { "X-Admin-Token": token },
    validateStatus: () => true,
  });
  return r.status === 200;
};
