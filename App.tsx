import Navbar from "./components/Navbar"
import LoadingOverlay from "./components/LoadingOverlay"
import UploadPage from "./pages/UploadPage"
import AnalysisPage from "./pages/AnalysisPage"
import TemplatesPage from "./pages/TemplatesPage"
import ProcessingPage from "./pages/ProcessingPage"
import OutputPage from "./pages/OutputPage"
import LearningPage from "./pages/LearningPage"
import AuthPage from "./pages/AuthPage"
import RewritePage from "./pages/RewritePage"
import { useStore } from "./store/useStore"
import { AnimatePresence, motion } from "framer-motion"

export default function App() {
  const { currentPage, isAnalyzing } = useStore()

  const renderPage = () => {
    switch (currentPage) {
      case "upload":
        return <UploadPage key="upload" />
      case "analysis":
        return <AnalysisPage key="analysis" />
      case "templates":
        return <TemplatesPage key="templates" />
      case "processing":
        return <ProcessingPage key="processing" />
      case "rewrite":
        return <RewritePage key="rewrite" />
      case "output":
        return <OutputPage key="output" />
      case "learning":
        return <LearningPage key="learning" />
      case "auth":
        return <AuthPage key="auth" />
      default:
        return <UploadPage key="default" />
    }
  }

  return (
    <div className="min-h-screen">
      {isAnalyzing && <LoadingOverlay />}
      <Navbar />
      <main className="pb-12 bg-[#f8fafc]">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentPage}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
          >
            {renderPage()}
          </motion.div>
        </AnimatePresence>
      </main>
      <footer className="print:hidden border-t border-purple-100 bg-white/50 backdrop-blur-sm py-6">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-sm text-gray-400">
            &copy; 2026 ResumeIQ &mdash; AI-Powered Resume Optimization Platform
          </p>
        </div>
      </footer>
    </div>
  )
}
