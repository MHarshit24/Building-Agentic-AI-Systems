-- FinDoc Analyzer Sample Database Schema and Data
-- This SQL file contains structured financial data for TechVision Corporation
-- to complement the Annual Financial Report document

-- =============================================================================
-- FINANCIAL STATEMENTS TABLES
-- =============================================================================

-- Table: financial_statements
-- Stores high-level financial statement data by period
CREATE TABLE IF NOT EXISTS financial_statements (
    statement_id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER,  -- NULL for annual statements
    statement_type VARCHAR(50) NOT NULL,  -- 'Income Statement', 'Balance Sheet', 'Cash Flow'
    filing_date DATE NOT NULL,
    report_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_name, fiscal_year, fiscal_quarter, statement_type)
);

-- Table: income_statement_line_items
-- Detailed line items from income statements
CREATE TABLE IF NOT EXISTS income_statement_line_items (
    line_item_id SERIAL PRIMARY KEY,
    statement_id INTEGER REFERENCES financial_statements(statement_id),
    line_item_name VARCHAR(255) NOT NULL,
    line_item_category VARCHAR(100),  -- 'Revenue', 'Cost', 'Operating Expense', etc.
    amount_usd DECIMAL(15, 2) NOT NULL,
    percentage_of_revenue DECIMAL(5, 2),
    notes TEXT
);

-- Table: balance_sheet_items
-- Balance sheet accounts by period
CREATE TABLE IF NOT EXISTS balance_sheet_items (
    balance_item_id SERIAL PRIMARY KEY,
    statement_id INTEGER REFERENCES financial_statements(statement_id),
    account_category VARCHAR(100) NOT NULL,  -- 'Current Assets', 'Liabilities', etc.
    account_name VARCHAR(255) NOT NULL,
    amount_usd DECIMAL(15, 2) NOT NULL,
    is_debit BOOLEAN NOT NULL
);

-- Table: financial_ratios
-- Calculated financial ratios and metrics
CREATE TABLE IF NOT EXISTS financial_ratios (
    ratio_id SERIAL PRIMARY KEY,
    statement_id INTEGER REFERENCES financial_statements(statement_id),
    ratio_name VARCHAR(100) NOT NULL,
    ratio_value DECIMAL(10, 4) NOT NULL,
    industry_benchmark DECIMAL(10, 4),
    ratio_category VARCHAR(50)  -- 'Profitability', 'Liquidity', 'Efficiency', 'Leverage'
);

-- Table: quarterly_revenue_breakdown
-- Detailed quarterly revenue by segment
CREATE TABLE IF NOT EXISTS quarterly_revenue_breakdown (
    revenue_id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER NOT NULL,
    segment_name VARCHAR(100) NOT NULL,
    revenue_usd DECIMAL(15, 2) NOT NULL,
    yoy_growth_percent DECIMAL(5, 2),
    segment_margin_percent DECIMAL(5, 2)
);

-- Table: risk_disclosures
-- Risk factors mentioned in financial reports
CREATE TABLE IF NOT EXISTS risk_disclosures (
    risk_id SERIAL PRIMARY KEY,
    statement_id INTEGER REFERENCES financial_statements(statement_id),
    risk_category VARCHAR(100) NOT NULL,
    risk_title VARCHAR(255) NOT NULL,
    risk_description TEXT,
    severity_level VARCHAR(20),  -- 'High', 'Medium', 'Low'
    first_disclosed_date DATE
);

-- =============================================================================
-- SAMPLE DATA - TechVision Corporation
-- =============================================================================

-- Insert Annual Financial Statements
INSERT INTO financial_statements (company_name, fiscal_year, fiscal_quarter, statement_type, filing_date, report_url) VALUES
('TechVision Corporation', 2024, NULL, 'Income Statement', '2025-02-15', 'https://investor.techvision.com/2024-annual'),
('TechVision Corporation', 2024, NULL, 'Balance Sheet', '2025-02-15', 'https://investor.techvision.com/2024-annual'),
('TechVision Corporation', 2023, NULL, 'Income Statement', '2024-02-15', 'https://investor.techvision.com/2023-annual'),
('TechVision Corporation', 2023, NULL, 'Balance Sheet', '2024-02-15', 'https://investor.techvision.com/2023-annual'),
('TechVision Corporation', 2022, NULL, 'Income Statement', '2023-02-15', 'https://investor.techvision.com/2022-annual');

-- Insert Quarterly Financial Statements (2024)
INSERT INTO financial_statements (company_name, fiscal_year, fiscal_quarter, statement_type, filing_date, report_url) VALUES
('TechVision Corporation', 2024, 1, 'Income Statement', '2024-04-30', 'https://investor.techvision.com/2024-q1'),
('TechVision Corporation', 2024, 2, 'Income Statement', '2024-07-31', 'https://investor.techvision.com/2024-q2'),
('TechVision Corporation', 2024, 3, 'Income Statement', '2024-10-31', 'https://investor.techvision.com/2024-q3'),
('TechVision Corporation', 2024, 4, 'Income Statement', '2025-01-31', 'https://investor.techvision.com/2024-q4');

-- Insert Income Statement Line Items (2024 Annual)
INSERT INTO income_statement_line_items (statement_id, line_item_name, line_item_category, amount_usd, percentage_of_revenue) VALUES
(1, 'Total Revenue', 'Revenue', 1831500000.00, 100.00),
(1, 'Cloud Services Revenue', 'Revenue', 892000000.00, 48.70),
(1, 'Enterprise Software Revenue', 'Revenue', 654000000.00, 35.70),
(1, 'AI Solutions Revenue', 'Revenue', 285500000.00, 15.60),
(1, 'Cost of Revenue', 'Cost', 579700000.00, 31.60),
(1, 'Gross Profit', 'Gross Profit', 1251800000.00, 68.40),
(1, 'Research & Development', 'Operating Expense', 385200000.00, 21.00),
(1, 'Sales & Marketing', 'Operating Expense', 311400000.00, 17.00),
(1, 'General & Administrative', 'Operating Expense', 98900000.00, 5.40),
(1, 'Operating Income', 'Operating Income', 456300000.00, 24.90),
(1, 'Interest Income', 'Non-Operating Income', 18500000.00, 1.00),
(1, 'Interest Expense', 'Non-Operating Expense', 8200000.00, 0.40),
(1, 'Income Before Taxes', 'Pre-Tax Income', 466600000.00, 25.50),
(1, 'Income Tax Expense', 'Tax', 137900000.00, 7.50),
(1, 'Net Income', 'Net Income', 328700000.00, 17.95);

-- Insert Income Statement Line Items (2023 Annual)
INSERT INTO income_statement_line_items (statement_id, line_item_name, line_item_category, amount_usd, percentage_of_revenue) VALUES
(3, 'Total Revenue', 'Revenue', 1489300000.00, 100.00),
(3, 'Cloud Services Revenue', 'Revenue', 681000000.00, 45.70),
(3, 'Enterprise Software Revenue', 'Revenue', 554000000.00, 37.20),
(3, 'AI Solutions Revenue', 'Revenue', 254300000.00, 17.10),
(3, 'Cost of Revenue', 'Cost', 505700000.00, 34.00),
(3, 'Gross Profit', 'Gross Profit', 983600000.00, 66.00),
(3, 'Research & Development', 'Operating Expense', 312300000.00, 21.00),
(3, 'Sales & Marketing', 'Operating Expense', 253200000.00, 17.00),
(3, 'General & Administrative', 'Operating Expense', 76400000.00, 5.10),
(3, 'Operating Income', 'Operating Income', 341700000.00, 22.90),
(3, 'Interest Income', 'Non-Operating Income', 12400000.00, 0.80),
(3, 'Interest Expense', 'Non-Operating Expense', 6800000.00, 0.50),
(3, 'Income Before Taxes', 'Pre-Tax Income', 347300000.00, 23.30),
(3, 'Income Tax Expense', 'Tax', 102100000.00, 6.90),
(3, 'Net Income', 'Net Income', 245200000.00, 16.50);

-- Insert Balance Sheet Items (2024 Annual)
INSERT INTO balance_sheet_items (statement_id, account_category, account_name, amount_usd, is_debit) VALUES
-- Assets
(2, 'Current Assets', 'Cash and Cash Equivalents', 823400000.00, TRUE),
(2, 'Current Assets', 'Accounts Receivable', 412300000.00, TRUE),
(2, 'Current Assets', 'Inventory', 89700000.00, TRUE),
(2, 'Current Assets', 'Prepaid Expenses', 45200000.00, TRUE),
(2, 'Non-Current Assets', 'Property, Plant & Equipment', 567800000.00, TRUE),
(2, 'Non-Current Assets', 'Intangible Assets', 234500000.00, TRUE),
(2, 'Non-Current Assets', 'Goodwill', 456700000.00, TRUE),
(2, 'Non-Current Assets', 'Long-term Investments', 178900000.00, TRUE),
-- Liabilities
(2, 'Current Liabilities', 'Accounts Payable', 234100000.00, FALSE),
(2, 'Current Liabilities', 'Accrued Expenses', 167800000.00, FALSE),
(2, 'Current Liabilities', 'Deferred Revenue', 298500000.00, FALSE),
(2, 'Current Liabilities', 'Current Portion of Long-term Debt', 45000000.00, FALSE),
(2, 'Non-Current Liabilities', 'Long-term Debt', 312000000.00, FALSE),
(2, 'Non-Current Liabilities', 'Deferred Tax Liabilities', 89300000.00, FALSE),
-- Equity
(2, 'Shareholders Equity', 'Common Stock', 1000000.00, FALSE),
(2, 'Shareholders Equity', 'Additional Paid-in Capital', 845600000.00, FALSE),
(2, 'Shareholders Equity', 'Retained Earnings', 1136200000.00, FALSE);

-- Insert Financial Ratios (2024)
INSERT INTO financial_ratios (statement_id, ratio_name, ratio_value, industry_benchmark, ratio_category) VALUES
(1, 'Gross Margin', 68.40, 65.00, 'Profitability'),
(1, 'Operating Margin', 24.90, 20.00, 'Profitability'),
(1, 'Net Profit Margin', 17.95, 15.00, 'Profitability'),
(1, 'Return on Assets (ROA)', 11.53, 10.00, 'Profitability'),
(1, 'Return on Equity (ROE)', 16.57, 14.00, 'Profitability'),
(2, 'Current Ratio', 1.96, 2.00, 'Liquidity'),
(2, 'Quick Ratio', 1.84, 1.50, 'Liquidity'),
(2, 'Debt to Equity Ratio', 0.18, 0.30, 'Leverage'),
(2, 'Interest Coverage Ratio', 55.65, 25.00, 'Leverage'),
(1, 'Asset Turnover', 0.64, 0.70, 'Efficiency'),
(2, 'Inventory Turnover', 6.46, 8.00, 'Efficiency');

-- Insert Financial Ratios (2023)
INSERT INTO financial_ratios (statement_id, ratio_name, ratio_value, industry_benchmark, ratio_category) VALUES
(3, 'Gross Margin', 66.00, 65.00, 'Profitability'),
(3, 'Operating Margin', 22.90, 20.00, 'Profitability'),
(3, 'Net Profit Margin', 16.50, 15.00, 'Profitability'),
(3, 'Return on Assets (ROA)', 9.87, 10.00, 'Profitability'),
(3, 'Return on Equity (ROE)', 14.23, 14.00, 'Profitability');

-- Insert Quarterly Revenue Breakdown (2024)
INSERT INTO quarterly_revenue_breakdown (company_name, fiscal_year, fiscal_quarter, segment_name, revenue_usd, yoy_growth_percent, segment_margin_percent) VALUES
-- Q1 2024
('TechVision Corporation', 2024, 1, 'Cloud Services', 421300000.00, 28.50, 71.20),
('TechVision Corporation', 2024, 1, 'Enterprise Software', 158400000.00, 15.20, 67.80),
('TechVision Corporation', 2024, 1, 'AI Solutions', 66000000.00, 24.30, 62.50),
-- Q2 2024
('TechVision Corporation', 2024, 2, 'Cloud Services', 445700000.00, 30.80, 72.10),
('TechVision Corporation', 2024, 2, 'Enterprise Software', 162500000.00, 17.90, 68.30),
('TechVision Corporation', 2024, 2, 'AI Solutions', 69500000.00, 26.70, 63.40),
-- Q3 2024
('TechVision Corporation', 2024, 3, 'Cloud Services', 468200000.00, 32.40, 72.80),
('TechVision Corporation', 2024, 3, 'Enterprise Software', 165800000.00, 19.50, 68.90),
('TechVision Corporation', 2024, 3, 'AI Solutions', 73200000.00, 28.10, 64.20),
-- Q4 2024
('TechVision Corporation', 2024, 4, 'Cloud Services', 495800000.00, 33.90, 73.50),
('TechVision Corporation', 2024, 4, 'Enterprise Software', 167300000.00, 20.30, 69.40),
('TechVision Corporation', 2024, 4, 'AI Solutions', 76800000.00, 29.80, 65.10);

-- Q1-Q4 2023 (for comparison)
INSERT INTO quarterly_revenue_breakdown (company_name, fiscal_year, fiscal_quarter, segment_name, revenue_usd, yoy_growth_percent, segment_margin_percent) VALUES
('TechVision Corporation', 2023, 1, 'Cloud Services', 328000000.00, 25.30, 69.50),
('TechVision Corporation', 2023, 1, 'Enterprise Software', 137500000.00, 12.40, 66.20),
('TechVision Corporation', 2023, 1, 'AI Solutions', 53100000.00, 31.20, 60.80),
('TechVision Corporation', 2023, 2, 'Cloud Services', 351000000.00, 26.80, 70.20),
('TechVision Corporation', 2023, 2, 'Enterprise Software', 137800000.00, 13.60, 66.90),
('TechVision Corporation', 2023, 2, 'AI Solutions', 54900000.00, 33.50, 61.30),
('TechVision Corporation', 2023, 3, 'Cloud Services', 378500000.00, 28.20, 70.80),
('TechVision Corporation', 2023, 3, 'Enterprise Software', 138700000.00, 14.80, 67.40),
('TechVision Corporation', 2023, 3, 'AI Solutions', 57100000.00, 35.70, 61.90),
('TechVision Corporation', 2023, 4, 'Cloud Services', 402500000.00, 29.60, 71.40),
('TechVision Corporation', 2023, 4, 'Enterprise Software', 139000000.00, 16.20, 68.00),
('TechVision Corporation', 2023, 4, 'AI Solutions', 59200000.00, 37.80, 62.40);

-- Insert Risk Disclosures
INSERT INTO risk_disclosures (statement_id, risk_category, risk_title, risk_description, severity_level, first_disclosed_date) VALUES
(1, 'Market Risk', 'Market Competition', 
 'The technology sector remains highly competitive with rapid innovation cycles. Increased competition from established players and new market entrants could pressure our pricing power and market share.', 
 'High', '2022-02-15'),
 
(1, 'Economic Risk', 'Economic Uncertainty', 
 'Global economic conditions, including inflation, interest rate volatility, and potential recession risks, may impact customer spending on technology solutions and affect our revenue growth trajectory.', 
 'High', '2023-02-15'),
 
(1, 'Operational Risk', 'Cybersecurity Threats', 
 'As a technology company, we face ongoing cybersecurity risks. Any significant data breach or security incident could result in financial losses, reputational damage, and regulatory penalties.', 
 'High', '2020-02-15'),
 
(1, 'Regulatory Risk', 'Regulatory Compliance', 
 'Evolving data privacy regulations, AI governance frameworks, and industry-specific compliance requirements may increase operational costs and limit our ability to deploy certain technologies in regulated markets.', 
 'Medium', '2023-08-15'),
 
(1, 'Financial Risk', 'Foreign Exchange Risk', 
 'We conduct business in multiple currencies. Fluctuations in foreign exchange rates could adversely affect our revenue, expenses, and financial position.', 
 'Medium', '2021-02-15'),
 
(1, 'Operational Risk', 'Talent Acquisition and Retention', 
 'Our success depends on attracting and retaining highly skilled technical talent in a competitive labor market. Failure to do so could impact our ability to innovate and deliver products.', 
 'Medium', '2022-08-15');

-- =============================================================================
-- USEFUL QUERIES FOR RAG SYSTEM TESTING
-- =============================================================================

-- Query 1: Year-over-year revenue comparison
-- SELECT fiscal_year, amount_usd 
-- FROM income_statement_line_items 
-- WHERE line_item_name = 'Total Revenue' 
-- ORDER BY fiscal_year;

-- Query 2: Quarterly revenue trends by segment
-- SELECT fiscal_year, fiscal_quarter, segment_name, revenue_usd, yoy_growth_percent
-- FROM quarterly_revenue_breakdown
-- WHERE fiscal_year IN (2023, 2024)
-- ORDER BY fiscal_year, fiscal_quarter, segment_name;

-- Query 3: Profitability ratios comparison
-- SELECT fs.fiscal_year, fr.ratio_name, fr.ratio_value, fr.industry_benchmark
-- FROM financial_ratios fr
-- JOIN financial_statements fs ON fr.statement_id = fs.statement_id
-- WHERE fr.ratio_category = 'Profitability'
-- ORDER BY fs.fiscal_year, fr.ratio_name;

-- Query 4: High severity risks
-- SELECT risk_category, risk_title, risk_description
-- FROM risk_disclosures
-- WHERE severity_level = 'High'
-- ORDER BY risk_category;

-- Query 5: Balance sheet summary
-- SELECT account_category, SUM(amount_usd) as total_amount
-- FROM balance_sheet_items
-- WHERE statement_id = 2  -- 2024 Balance Sheet
-- GROUP BY account_category
-- ORDER BY account_category;

-- =============================================================================
-- END OF SAMPLE DATA
-- =============================================================================
