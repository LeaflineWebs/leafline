"use strict";
const { contextBridge, ipcRenderer } = require("electron");
// What the page may ask Electron for: a Save dialog for CSV exports, saving an invoice PDF, and the app-update controls.
contextBridge.exposeInMainWorld("leafline", {
  saveCsv: (defaultName) => ipcRenderer.invoke("save-csv", String(defaultName || "leads.csv")),
  savePdf: (defaultName, bytes) => ipcRenderer.invoke("save-pdf", String(defaultName || "invoice.pdf"), bytes),
  appInfo: () => ipcRenderer.invoke("app-info"),
  status: () => ipcRenderer.invoke("update-status"),
  checkUpdate: () => ipcRenderer.invoke("update-check"),
  installUpdate: () => ipcRenderer.invoke("update-install"),
  onUpdate: (cb) => { ipcRenderer.on("update-status", (_e, s) => { try { cb(s); } catch (_) {} }); },
});
