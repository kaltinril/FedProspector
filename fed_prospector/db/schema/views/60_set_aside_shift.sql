-- views/60_set_aside_shift.sql
-- Set-aside shift analysis: compares current opportunity set-aside with predecessor contract

USE fed_contracts;

CREATE OR REPLACE VIEW v_set_aside_shift AS
SELECT
    o.notice_id,
    o.solicitation_number,
    o.set_aside_code              AS current_set_aside_code,
    o.set_aside_description       AS current_set_aside_description,
    fc.set_aside_type             AS predecessor_set_aside_type,
    fc.vendor_name                AS predecessor_vendor_name,
    fc.vendor_uei                 AS predecessor_vendor_uei,
    fc.date_signed                AS predecessor_date_signed,
    fc.base_and_all_options       AS predecessor_value,
    -- Shift detection: 1 if set-aside changed, 0 if same, NULL if no predecessor
    CASE
        WHEN fc.set_aside_type IS NULL THEN NULL
        WHEN fc.set_aside_type != o.set_aside_code THEN 1
        ELSE 0
    END AS shift_detected
FROM opportunity o
LEFT JOIN (
    SELECT fc1.*
    FROM (
        SELECT fc.*,
               ROW_NUMBER() OVER (PARTITION BY solicitation_number
                                  ORDER BY date_signed DESC, contract_id DESC) AS rn
        FROM fpds_contract fc
        WHERE modification_number = '0'
          AND solicitation_number IS NOT NULL
          AND solicitation_number != ''
    ) fc1
    WHERE fc1.rn = 1
) fc ON o.solicitation_number = fc.solicitation_number
    AND o.solicitation_number IS NOT NULL
    AND o.solicitation_number != ''
WHERE o.active = 'Y';
