import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { SupabaseProvider } from './contexts/SupabaseContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import MarketingIdeas from './pages/MarketingIdeas'
import ContentManager from './pages/ContentManager'
import Analytics from './pages/Analytics'
import Profile from './pages/Profile'

function App() {
  return (
    <SupabaseProvider>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/marketing" element={<MarketingIdeas />} />
            <Route path="/content" element={<ContentManager />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/profile" element={<Profile />} />
          </Routes>
        </Layout>
      </Router>
    </SupabaseProvider>
  )
}

export default App