CREATE DATABASE IF NOT EXISTS video_db;
USE video_db;

CREATE TABLE IF NOT EXISTS videos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255),
    status ENUM('UPLOADED', 'PROCESSING', 'COMPLETED') DEFAULT 'UPLOADED',
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS video_qualities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    video_id INT,
    quality VARCHAR(10),
    file_path VARCHAR(255),
    FOREIGN KEY (video_id) REFERENCES videos(id),
    UNIQUE KEY unique_video_quality (video_id, quality)
);