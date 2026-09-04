import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import AddTarget from "./pages/AddTarget";
import Dashboard from "./pages/Dashboard";
import NewScan from "./pages/NewScan";
import Playground from "./pages/Playground";
import Report from "./pages/Report";
import ScanDetail from "./pages/ScanDetail";
import Targets from "./pages/Targets";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="playground" element={<Playground />} />
          <Route path="targets" element={<Targets />} />
          <Route path="targets/new" element={<AddTarget />} />
          <Route path="scans/new" element={<NewScan />} />
          <Route path="scans/:scanId" element={<ScanDetail />} />
          <Route path="reports/:scanId" element={<Report />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}