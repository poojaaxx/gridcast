import { Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import ProtectedRoute from "./components/ProtectedRoute";
import RegionProvider from "./state/RegionProvider";
import UIProvider from "./state/UIProvider";
import ToastProvider from "./state/ToastProvider";
import AuthProvider from "./state/AuthProvider";
import Overview from "./pages/Overview";
import ForecastExplorer from "./pages/ForecastExplorer";
import ModelPerformance from "./pages/ModelPerformance";
import DataExplorer from "./pages/DataExplorer";
import ModelMonitoring from "./pages/ModelMonitoring";
import Login from "./pages/Login";
import Admin from "./pages/Admin";

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <UIProvider>
          <RegionProvider>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route
                path="*"
                element={
                  <ProtectedRoute>
                    <div className="app-shell flex h-screen w-screen overflow-hidden">
                      <Sidebar />
                      <main className="flex-1 overflow-y-auto min-w-0">
                        <Routes>
                          <Route path="/" element={<Overview />} />
                          <Route path="/forecasts" element={<ForecastExplorer />} />
                          <Route path="/performance" element={<ModelPerformance />} />
                          <Route path="/data" element={<DataExplorer />} />
                          <Route path="/monitoring" element={<ModelMonitoring />} />
                          <Route
                            path="/admin"
                            element={
                              <ProtectedRoute requireAdmin>
                                <Admin />
                              </ProtectedRoute>
                            }
                          />
                        </Routes>
                      </main>
                    </div>
                  </ProtectedRoute>
                }
              />
            </Routes>
          </RegionProvider>
        </UIProvider>
      </AuthProvider>
    </ToastProvider>
  );
}
