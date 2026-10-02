/** Composition entry: business screens are registered outside the shared Agent UI. */
import { Route } from 'react-router-dom'
import { MerchantsPage } from './pages/MerchantsPage'
import { StorefrontPage } from './pages/StorefrontPage'
import { BookingsPage, BuyerOrdersPage } from './pages/BookingsPage'
import { MemoriesPage } from './pages/MemoriesPage'
import { CommerceAgentPage, QuoteConfirmationPage } from './pages/CommerceAgentPage'
import { AgentConnectionsPage } from './pages/AgentConnectionsPage'
import { CommerceOperationsPage } from './pages/CommerceOperationsPage'

export function commerceRoutes() {
  return [
    <Route key="merchants" path="/merchants" element={<MerchantsPage />} />,
    <Route key="storefront" path="/stores/:merchantId" element={<StorefrontPage />} />,
    <Route key="booking" path="/stores/:merchantId/book/:serviceId" element={<BookingsPage />} />,
    <Route key="orders" path="/orders" element={<BuyerOrdersPage />} />,
    <Route key="memory" path="/memories" element={<MemoriesPage />} />,
    <Route key="agent" path="/agent-commerce" element={<CommerceAgentPage />} />,
    <Route key="quote" path="/quotes/:quoteId" element={<QuoteConfirmationPage />} />,
    <Route key="connections" path="/connections" element={<AgentConnectionsPage />} />,
    <Route key="operations" path="/operations" element={<CommerceOperationsPage />} />,
  ]
}
