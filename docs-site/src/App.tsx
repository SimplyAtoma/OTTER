import Navbar from './components/Navbar'
import Hero from './components/Hero'
import Features from './components/Features'
import Architecture from './components/Architecture'
import PipelineDemo from './components/PipelineDemo'
import GettingStarted from './components/GettingStarted'
import Footer from './components/Footer'
import './App.css'

export default function App() {
  return (
    <div className="app">
      <Navbar />
      <main>
        <Hero />
        <Features />
        <Architecture />
        <PipelineDemo />
        <GettingStarted />
      </main>
      <Footer />
    </div>
  )
}
