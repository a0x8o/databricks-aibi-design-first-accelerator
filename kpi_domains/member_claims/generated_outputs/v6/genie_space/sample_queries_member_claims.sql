SELECT MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6`;

SELECT service_month, MEASURE(`Total Claims`) AS total_claims FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY service_month;

SELECT claim_type, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY total_paid_amount DESC;

SELECT MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` WHERE claim_type = 'Institutional';

SELECT benefit_category, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY total_paid_amount DESC LIMIT 5;

SELECT adjudication_status, MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY denial_rate DESC;

SELECT line_status, MEASURE(`Total Claim Lines`) AS total_claim_lines, MEASURE(`Clean Claim Rate`) AS clean_claim_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY total_claim_lines DESC;

SELECT MEASURE(`Payment-to-Billed Ratio`) AS payment_to_billed_ratio FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` WHERE benefit_level = 'In Network';

SELECT rendering_provider_specialty, MEASURE(`Average Paid per Claim`) AS average_paid_per_claim FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY average_paid_per_claim DESC LIMIT 7;

SELECT service_month, MEASURE(`Inpatient Paid Amount`) AS inpatient_paid_amount, MEASURE(`Outpatient Paid Amount`) AS outpatient_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY service_month;

SELECT MEASURE(`Active Enrolled Members`) AS active_enrolled_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6`;

SELECT line_of_business, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` GROUP BY ALL ORDER BY active_members DESC;

SELECT member_state, MEASURE(`Members by Geography`) AS members_by_geography FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` GROUP BY ALL ORDER BY members_by_geography DESC LIMIT 8;

SELECT MEASURE(`New Member Enrollment`) AS new_member_enrollment FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` WHERE line_of_business = 'Medicare Advantage';

SELECT service_month, MEASURE(`Member Months`) AS member_months FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` GROUP BY ALL ORDER BY service_month;

SELECT plan_id, enrollment_status, MEASURE(`Active Enrolled Members`) AS active_enrolled_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` GROUP BY ALL ORDER BY active_enrolled_members DESC LIMIT 10;
