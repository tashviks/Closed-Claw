interface ElectronAPI {
  getAppVersion: () => Promise<string>
  openExternal: (url: string) => Promise<void>
  showSaveDialog: (options: object) => Promise<{ canceled: boolean; filePath?: string }>
  showOpenDialog: (options: object) => Promise<{ canceled: boolean; filePaths: string[] }>
  readFile: (path: string) => Promise<{ success: boolean; data?: string; error?: string }>
  writeFile: (path: string, content: string) => Promise<{ success: boolean; error?: string }>
}

interface Window {
  electronAPI?: ElectronAPI
}
