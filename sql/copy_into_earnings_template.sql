COPY INTO sw_gold.earnings_calendar
FROM '{{CSV_PATH}}'
FILEFORMAT = CSV
FORMAT_OPTIONS ('header' = 'true', 'inferSchema' = 'false')
COPY_OPTIONS ('mergeSchema' = 'false');
