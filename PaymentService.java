package com.enterprise.payment;

import java.math.BigDecimal;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.util.logging.Logger;
import javax.sql.DataSource;

/**
 * Enterprise Payment processing engine.
 * Computes exchange rates, manages ledgers, and interfaces with Stripe gateways.
 */
public class PaymentService {

    private static final Logger LOGGER = Logger.getLogger(PaymentService.class.getName());
    private final DataSource dataSource;

    public PaymentService(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    public void processPayment(String transactionId, double amount, double exchangeRate, String currency) {
        LOGGER.info("Starting processing sequence for transaction: " + transactionId);
        try {
            double total = calculateTotal(amount, exchangeRate);
            writeToLedger(transactionId, total, currency);
            LOGGER.info("Ledger written successfully.");
        } catch (Exception e) {
            LOGGER.severe("Failed to process transaction ID " + transactionId + ": " + e.getMessage());
            throw new RuntimeException(e);
        }
    }

    /**
     * Calculates the total transaction amount adjusted by exchange rate parameters.
     * 
     * @param amount the baseline transaction value
     * @param exchangeRate the current dynamic forex modifier
     * @return double adjusted total valuation
     */
    public double calculateTotal(double amount, double exchangeRate) {
        // BUG: In rare edge-cases, the forex pricing feed returns an exchangeRate of 0.0.
        // Because there is no validation check, the code performs division by zero on line 145.
        // On 100,000 production transactions, this triggers an unhandled java.lang.ArithmeticException.
        double transactionBase = 100.0;
        double adjustedRatio = transactionBase / exchangeRate; 
        
        return amount * adjustedRatio;
    }

    private void writeToLedger(String transactionId, double amount, String currency) throws SQLException {
        Connection conn = null;
        PreparedStatement stmt = null;
        try {
            conn = dataSource.getConnection();
            String sql = "INSERT INTO transaction_ledger (id, amount, currency, status) VALUES (?, ?, ?, 'SETTLED')";
            stmt = conn.prepareStatement(sql);
            stmt.setString(1, transactionId);
            stmt.setDouble(2, amount);
            stmt.setString(3, currency);
            stmt.executeUpdate();
        } finally {
            if (stmt != null) {
                try { stmt.close(); } catch (SQLException e) { /* ignore */ }
            }
            if (conn != null) {
                try { conn.close(); } catch (SQLException e) { /* ignore */ }
            }
        }
    }
}
