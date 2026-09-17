SELECT MEASURE(`Total Claims`) AS total_claims, MEASURE(`Total Claim Lines`) AS total_claim_lines, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v11;

SELECT `Claim Type`, MEASURE(`Total Claims`) AS total_claims, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v11 GROUP BY `Claim Type` ORDER BY total_paid_amount DESC;

SELECT `Service Month`, MEASURE(`Total Paid Amount`) AS total_paid_amount, MEASURE(`Average Paid per Claim`) AS average_paid_per_claim FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v11 GROUP BY `Service Month` ORDER BY `Service Month`;

SELECT `Benefit Category`, MEASURE(`Total Claim Lines`) AS total_claim_lines, MEASURE(`Denial Rate`) AS denial_rate FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v11 GROUP BY `Benefit Category` ORDER BY denial_rate DESC;

SELECT `Claim Type`, MEASURE(`Clean Claim Rate`) AS clean_claim_rate, MEASURE(`Payment-to-Billed Ratio`) AS payment_to_billed_ratio, MEASURE(`Payment-to-Allowed Ratio`) AS payment_to_allowed_ratio FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v11 GROUP BY `Claim Type` ORDER BY `Claim Type`;

SELECT `Rendering Provider Specialty`, MEASURE(`Total Paid Amount`) AS total_paid_amount, MEASURE(`Participating Provider Rate`) AS participating_provider_rate FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v11 GROUP BY `Rendering Provider Specialty` ORDER BY total_paid_amount DESC LIMIT 10;

SELECT MEASURE(`Inpatient Paid Amount`) AS inpatient_paid_amount, MEASURE(`Outpatient Paid Amount`) AS outpatient_paid_amount, MEASURE(`Average Paid per Member`) AS average_paid_per_member, MEASURE(`Claims per Member`) AS claims_per_member FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v11;

SELECT `Place of Service`, MEASURE(`Lines per Claim`) AS lines_per_claim, MEASURE(`Total Claim Lines`) AS total_claim_lines FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v11 GROUP BY `Place of Service` ORDER BY total_claim_lines DESC;

SELECT MEASURE(`New Member Enrollment`) AS new_member_enrollment, MEASURE(`Active Members`) AS active_members FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v11;

SELECT `Line of Business`, MEASURE(`Active Members`) AS active_members, MEASURE(`New Member Enrollment`) AS new_member_enrollment FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v11 GROUP BY `Line of Business` ORDER BY active_members DESC;

SELECT `Member State`, MEASURE(`Members by Geography`) AS members_by_geography FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v11 GROUP BY `Member State` ORDER BY members_by_geography DESC;

SELECT `Service Month`, `Line of Business`, MEASURE(`Active Members`) AS active_members FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v11 GROUP BY `Service Month`, `Line of Business` ORDER BY `Service Month`, active_members DESC;
