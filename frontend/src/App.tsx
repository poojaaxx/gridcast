import { Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import RegionProvider from "./state/RegionProvider";
import UIProvider from "./state/UIProvider";
import ToastProvider from "./state/ToastProvider";
import Overview from "./pages/Overview";
import ForecastExplorer from "./pages/ForecastExplorer";
import ModelPerformance from "./pages/ModelPerformance";
import DataExplorer from "./pages/DataExplorer";
import ModelMonitoring from "./pages/ModelMonitoring";

export default function App() {
  return (
    <ToastProvider>
      <UIProvider>
        <RegionProvider>
          <div className="app-shell flex h-screen w-screen overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto min-w-0">
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route path="/forecasts" element={<ForecastExplorer />} />
                <Route path="/performance" element={<ModelPerformance />} />
                <Route path="/data" element={<DataExplorer />} />
                <Route path="/monitoring" element={<ModelMonitoring />} />
              </Routes>
            </main>
          </div>
        </RegionProvider>
      </UIProvider>
    </ToastProvider>
  );
}
