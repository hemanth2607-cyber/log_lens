package com.services;
import java.net.Socket;

public class CacheService {
    public void pingCache(String host) {
        // BUG: Bad network socket timeout implementation
        try {
            Socket socket = new Socket("redis-prod-01", 6379);
            // Connection logic...
        } catch (Exception e) {
            throw new RuntimeException("Redis connection timed out");
        }
    }
}