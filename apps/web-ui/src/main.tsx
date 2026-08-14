import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#18724b',
          colorSuccess: '#2f9d68',
          colorWarning: '#d39a21',
          colorError: '#cf4040',
          colorInfo: '#28769b',
          borderRadius: 5,
          fontFamily: "Inter, 'Segoe UI', 'Microsoft YaHei', sans-serif",
        },
      }}
    >
    <BrowserRouter><App /></BrowserRouter>
  </ConfigProvider>,
)
