# NovaMart ER Diagram Description

- sellers 1:N products
- customers 1:N orders
- orders 1:N order_items
- products 1:N order_items
- sellers 1:N order_items
- orders 1:N payments
- orders 1:N shipments
- orders 1:N returns
- order_items 1:N returns
- customers 1:N support_tickets
- orders 1:N support_tickets (nullable)
- products 1:N support_tickets (nullable)
- marketing_campaigns 1:N leads
- marketing_campaigns 1:N marketing_events
- customers 1:N marketing_events
- leads may reference customers and sellers where applicable

All entities belong to the same fictional NovaMart business.
