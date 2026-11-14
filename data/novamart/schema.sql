-- AgentOps AI / NovaMart synthetic PostgreSQL schema
-- All data is synthetic and intended for the academic AgentOps AI project.

CREATE TABLE customers (
    customer_id VARCHAR(20) PRIMARY KEY, first_name VARCHAR(80) NOT NULL, last_name VARCHAR(80) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL, phone VARCHAR(20), age INTEGER, gender VARCHAR(30),
    city VARCHAR(80), state VARCHAR(80), country VARCHAR(80), customer_segment VARCHAR(30),
    acquisition_channel VARCHAR(50), registration_date DATE, loyalty_tier VARCHAR(20),
    lifetime_value NUMERIC(14,2), preferred_category VARCHAR(80), status VARCHAR(20)
);
CREATE TABLE sellers (
    seller_id VARCHAR(20) PRIMARY KEY, seller_name VARCHAR(150) NOT NULL, seller_category VARCHAR(80),
    seller_city VARCHAR(80), seller_state VARCHAR(80), onboarding_date DATE, acquisition_channel VARCHAR(50),
    seller_segment VARCHAR(30), rating NUMERIC(3,2), active_status VARCHAR(20),
    total_orders INTEGER DEFAULT 0, total_revenue NUMERIC(16,2) DEFAULT 0
);
CREATE TABLE products (
    product_id VARCHAR(20) PRIMARY KEY, seller_id VARCHAR(20) REFERENCES sellers(seller_id),
    product_name VARCHAR(200), category VARCHAR(80), subcategory VARCHAR(80), brand VARCHAR(80),
    description_short TEXT, unit_price NUMERIC(14,2), cost_price NUMERIC(14,2),
    inventory_quantity INTEGER, launch_date DATE, rating NUMERIC(3,2), warranty_months INTEGER,
    active_status VARCHAR(20)
);
CREATE TABLE marketing_campaigns (
    campaign_id VARCHAR(20) PRIMARY KEY, campaign_name VARCHAR(200), campaign_type VARCHAR(50),
    objective VARCHAR(100), start_date DATE, end_date DATE, target_segment VARCHAR(30),
    target_region VARCHAR(30), budget NUMERIC(16,2), actual_spend NUMERIC(16,2),
    impressions BIGINT, clicks BIGINT, leads_generated INTEGER, conversions INTEGER,
    revenue_generated NUMERIC(16,2), status VARCHAR(20)
);
CREATE TABLE leads (
    lead_id VARCHAR(20) PRIMARY KEY, campaign_id VARCHAR(20) REFERENCES marketing_campaigns(campaign_id),
    seller_id VARCHAR(20) REFERENCES sellers(seller_id), customer_id VARCHAR(20) REFERENCES customers(customer_id),
    lead_source VARCHAR(50), lead_date DATE, lead_score INTEGER, lead_stage VARCHAR(30),
    region VARCHAR(30), company_size VARCHAR(30), interested_category VARCHAR(80),
    conversion_status VARCHAR(30), conversion_date DATE, expected_value NUMERIC(14,2), actual_value NUMERIC(14,2)
);
CREATE TABLE marketing_events (
    event_id VARCHAR(20) PRIMARY KEY, campaign_id VARCHAR(20) REFERENCES marketing_campaigns(campaign_id),
    customer_id VARCHAR(20) REFERENCES customers(customer_id), event_type VARCHAR(50),
    event_timestamp TIMESTAMP, channel VARCHAR(50), device VARCHAR(30), campaign_content VARCHAR(100),
    conversion_flag BOOLEAN, revenue_attributed NUMERIC(14,2)
);
CREATE TABLE orders (
    order_id VARCHAR(20) PRIMARY KEY, customer_id VARCHAR(20) REFERENCES customers(customer_id),
    order_date DATE, order_status VARCHAR(30), payment_status VARCHAR(30), shipping_status VARCHAR(30),
    total_amount NUMERIC(14,2), discount_amount NUMERIC(14,2), tax_amount NUMERIC(14,2),
    shipping_amount NUMERIC(14,2), region VARCHAR(30), acquisition_channel VARCHAR(50)
);
CREATE TABLE order_items (
    order_item_id VARCHAR(30) PRIMARY KEY, order_id VARCHAR(20) REFERENCES orders(order_id),
    product_id VARCHAR(20) REFERENCES products(product_id), seller_id VARCHAR(20) REFERENCES sellers(seller_id),
    quantity INTEGER, unit_price NUMERIC(14,2), discount NUMERIC(14,2), item_total NUMERIC(14,2)
);
CREATE TABLE payments (
    payment_id VARCHAR(20) PRIMARY KEY, order_id VARCHAR(20) REFERENCES orders(order_id),
    payment_method VARCHAR(40), payment_date DATE, amount NUMERIC(14,2),
    payment_status VARCHAR(30), transaction_reference VARCHAR(50)
);
CREATE TABLE shipments (
    shipment_id VARCHAR(20) PRIMARY KEY, order_id VARCHAR(20) REFERENCES orders(order_id),
    carrier VARCHAR(50), shipment_date DATE, expected_delivery_date DATE,
    actual_delivery_date DATE, delivery_status VARCHAR(30), delay_days INTEGER, destination_region VARCHAR(30)
);
CREATE TABLE returns (
    return_id VARCHAR(20) PRIMARY KEY, order_id VARCHAR(20) REFERENCES orders(order_id),
    order_item_id VARCHAR(30) REFERENCES order_items(order_item_id), return_date DATE,
    return_reason VARCHAR(80), refund_amount NUMERIC(14,2), return_status VARCHAR(30),
    resolution_type VARCHAR(40)
);
CREATE TABLE support_tickets (
    ticket_id VARCHAR(20) PRIMARY KEY, customer_id VARCHAR(20) REFERENCES customers(customer_id),
    order_id VARCHAR(20) REFERENCES orders(order_id), product_id VARCHAR(20) REFERENCES products(product_id),
    ticket_date DATE, issue_category VARCHAR(80), priority VARCHAR(20), status VARCHAR(30),
    resolution_time_hours NUMERIC(10,2), assigned_team VARCHAR(50), satisfaction_score NUMERIC(3,1)
);

-- Production deployment should create the application role with a secret-managed password.
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO agentops_readonly;