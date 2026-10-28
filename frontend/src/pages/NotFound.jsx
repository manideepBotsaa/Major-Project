import { Link } from 'react-router-dom'
import { ArrowLeft, Compass } from 'lucide-react'

export default function NotFound() {
  return (
    <main className="not-found">
      <span className="not-found-mark"><Compass size={30} /></span>
      <span className="eyebrow">404 · OFF THE PATH</span>
      <h1>This page is not part of your workspace.</h1>
      <p>The link may be outdated, or the page may have moved. Your financial data is untouched.</p>
      <Link to="/" className="btn btn-primary"><ArrowLeft size={16} /> Return to overview</Link>
    </main>
  )
}
