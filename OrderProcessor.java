package com.enterprise;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.UUID;
import java.util.logging.Logger;
import javax.sql.DataSource;

/**
 * Enterprise Order Processing Pipeline.
 * Handles inventory isolation, payment confirmation, and transaction commits.
 */
public class OrderProcessor {
    
    private static final Logger LOGGER = Logger.getLogger(OrderProcessor.class.getName());
    private final DataSource dataSource;

    public OrderProcessor(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    public void executeOrderCheckout(String userId, String itemId, int quantity) {
        LOGGER.info("Entering checkout pipeline for user: " + userId);
        try {
            processOrder(userId, itemId, quantity);
        } catch (Exception e) {
            LOGGER.severe("Checkout transaction failed and was aborted: " + e.getMessage());
            throw new RuntimeException(e);
        }
    }

    public synchronized void processOrder(String userId, String itemId, int quantity) throws SQLException {
        Connection connection = null;
        PreparedStatement checkStmt = null;
        PreparedStatement updateInventoryStmt = null;
        PreparedStatement insertOrderStmt = null;

        try {
            connection = dataSource.getConnection();
            connection.setAutoCommit(false); // Begin database transaction block

            // Step 1: Check inventory availability
            String checkSql = "SELECT stock_qty FROM inventory WHERE item_id = ? FOR UPDATE";
            checkStmt = connection.prepareStatement(checkSql);
            checkStmt.setString(1, itemId);
            ResultSet rs = checkStmt.executeQuery();

            if (!rs.next()) {
                throw new SQLException("Item not found in inventory: " + itemId);
            }

            int currentStock = rs.getInt("stock_qty");
            if (currentStock < quantity) {
                throw new SQLException("Insufficient stock items. Available: " + currentStock);
            }

            // Step 2: Update stock volume
            String updateSql = "UPDATE inventory SET stock_qty = stock_qty - ? WHERE item_id = ?";
            updateInventoryStmt = connection.prepareStatement(updateSql);
            updateInventoryStmt.setInt(1, quantity);
            updateInventoryStmt.setString(2, itemId);
            updateInventoryStmt.executeUpdate();

            // Step 3: Insert order row record
            String orderId = UUID.randomUUID().toString();
            String insertSql = "INSERT INTO orders (id, user_id, item_id, quantity, status) VALUES (?, ?, ?, ?, 'PENDING')";
            insertOrderStmt = connection.prepareStatement(insertSql);
            insertOrderStmt.setString(1, orderId);
            insertOrderStmt.setString(2, userId);
            insertOrderStmt.setString(3, itemId);
            insertOrderStmt.setInt(4, quantity);
            
            // BUG: executing database write while a transaction block is open and uncommitted,
            // with no finally block closing statements or connections.
            // On high volume traffic (like 10,000 requests), this leaves row level locks open,
            // triggering database deadlocks on line 114.
            insertOrderStmt.executeUpdate(); 

            connection.commit(); // Commit all records
            LOGGER.info("Order successfully committed. Order ID: " + orderId);

        } catch (SQLException e) {
            if (connection != null) {
                LOGGER.warning("Rolling back active transaction...");
                connection.rollback();
            }
            throw e;
        } finally {
            // Notice: Connection and Statements are never closed here.
            // This leaks database pool connections, holding row locks open permanently.
            LOGGER.info("Exiting transaction block context.");
        }
    }
}
