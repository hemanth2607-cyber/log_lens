# generate_huge_data.py
import datetime
import os

def generate_100k_logs(filename="huge_production.log"):
    start_time = datetime.datetime(2024, 3, 30, 16, 0, 0)
    
    print("Generating 100,000 lines of system logs (writing directly to disk)...")
    
    # Using a buffered stream write to generate 100K lines in under 2 seconds
    with open(filename, "w", encoding="utf-8") as f:
        for i in range(1, 100001):
            # Calculate dynamic timestamp incrementing by 50ms per line
            timestamp = (start_time + datetime.timedelta(milliseconds=i*50)).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
            
            # --- INJECT ERROR 1: Line 25,400 (Database Pool Saturation) ---
            if i == 25400:
                f.write(f"{i}: {timestamp} ERROR [http-nio-8080-exec-115] com.zaxxer.hikari.pool.HikariPool - HikariPool-1 - Connection starvation critical threshold exceeded. Active: 50, Idle: 0, Blocked: 24\n")
            
            # --- INJECT ERROR 2: Line 72,150 (Arithmetic Divide-by-Zero inside PaymentService.java:145) ---
            elif i == 72150:
                f.write(f"{i}: {timestamp} ERROR [http-nio-8080-exec-242] com.enterprise.payment.PaymentService - Transaction failed due to unhandled execution exception inside calculation block\n")
            elif 72150 < i <= 72155:
                # Stack trace details
                if i == 72151:
                    f.write(f"{i}: java.lang.ArithmeticException: / by zero\n")
                elif i == 72152:
                    f.write(f"{i}: \tat com.enterprise.payment.PaymentService.calculateTotal(PaymentService.java:145) ~[classes/:na]\n")
                elif i == 72153:
                    f.write(f"{i}: \tat com.enterprise.payment.PaymentService.processPayment(PaymentService.java:75) ~[classes/:na]\n")
                elif i == 72154:
                    f.write(f"{i}: \tat com.enterprise.controller.PaymentController.charge(PaymentController.java:34) ~[classes/:na]\n")
                elif i == 72155:
                    f.write(f"{i}: \tat sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method) ~[na:1.8.0_292]\n")
            
            # --- INJECT ERROR 3: Line 95,800 (External Network Gateway Timeout) ---
            elif i == 95800:
                f.write(f"{i}: {timestamp} ERROR [http-nio-8080-exec-901] com.services.GatewayConnector - Remote write timed out after 15000ms while transmitting to api.stripe.com\n")
                
            # --- STANDARD ROUTINE BACKGROUND LOGS ---
            else:
                if i % 250 == 0:
                    f.write(f"{i}: {timestamp} INFO  [scheduler-thread-1] com.jobs.TelemetryScheduler - Prometheus cluster ping successful (1.2ms).\n")
                elif i % 150 == 0:
                    f.write(f"{i}: {timestamp} INFO  [scheduler-thread-2] com.jobs.TokenEviction - Evicted expired token sessions.\n")
                elif i % 11 == 0:
                    f.write(f"{i}: {timestamp} INFO  [http-nio-8080-exec-{i%50+1}] com.api.gateway.AuthFilter - Auth token verified.\n")
                else:
                    f.write(f"{i}: {timestamp} INFO  [http-nio-8080-exec-{i%50+1}] com.services.UserService - Profile read from Redis Cache.\n")

    print(f"Log file successfully generated: {filename} (100,000 lines, size: ~12 MB)")


def generate_source_code(filename="PaymentService.java"):
    code = """package com.enterprise.payment;

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
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Source file successfully generated: {filename} (165 lines)")

if __name__ == "__main__":
    generate_100k_logs()
    generate_source_code()
    print("\nStress-test data is ready. Start the web application to analyze.")