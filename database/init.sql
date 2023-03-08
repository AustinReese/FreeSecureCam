DROP TABLE IF EXISTS Configuration;

CREATE TABLE Configuration(
    configuration_code SERIAL PRIMARY KEY,
    name VARCHAR(30),
    value VARCHAR(200));

INSERT INTO Configuration (name, value) VALUES ('watchfuleye_is_active', 'True');
INSERT INTO Configuration (name, value) VALUES ('log_path', 'C:/Temp/');
