SELECT MEASURE(`Total Paid Amount`) AS `Total Paid Amount` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v9`;

SELECT `Service Month`, MEASURE(`Total Paid Amount`) AS `Total Paid Amount` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v9` GROUP BY ALL ORDER BY `Service Month`;

SELECT `Claim Type`, MEASURE(`Total Claims`) AS `Total Claims` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v9` GROUP BY ALL ORDER BY `Total Claims` DESC;

SELECT MEASURE(`Denial Rate`) AS `Denial Rate` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v9` WHERE `Claim Type` = 'Institutional';

SELECT `Benefit Category`, MEASURE(`Total Paid Amount`) AS `Total Paid Amount` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v9` GROUP BY ALL ORDER BY `Total Paid Amount` DESC LIMIT 5;

SELECT `Claim Type`, MEASURE(`Denial Rate`) AS `Denial Rate` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v9` GROUP BY ALL ORDER BY `Denial Rate` DESC;

SELECT `Line Status`, MEASURE(`Total Claim Lines`) AS `Total Claim Lines`, MEASURE(`Denied Lines`) AS `Denied Lines` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v9` GROUP BY ALL ORDER BY `Total Claim Lines` DESC;

SELECT `Claim Type`, MEASURE(`Clean Claim Rate`) AS `Clean Claim Rate` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v9` GROUP BY ALL ORDER BY `Clean Claim Rate` DESC;

SELECT `Benefit Level`, MEASURE(`Payment-to-Billed Ratio`) AS `Payment-to-Billed Ratio`, MEASURE(`Payment-to-Allowed Ratio`) AS `Payment-to-Allowed Ratio` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v9` GROUP BY ALL ORDER BY `Payment-to-Billed Ratio` DESC;

SELECT `Rendering Provider Specialty`, MEASURE(`Participating Provider Rate`) AS `Participating Provider Rate` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v9` GROUP BY ALL ORDER BY `Participating Provider Rate` DESC LIMIT 10;

SELECT MEASURE(`Active Members`) AS `Active Members` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v9`;

SELECT `Line Of Business`, MEASURE(`Active Members`) AS `Active Members` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v9` GROUP BY ALL ORDER BY `Active Members` DESC;

SELECT `Member State`, MEASURE(`Active Members`) AS `Active Members` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v9` GROUP BY ALL ORDER BY `Active Members` DESC LIMIT 10;

SELECT `Service Month`, MEASURE(`New Member Enrollment`) AS `New Member Enrollment` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v9` GROUP BY ALL ORDER BY `Service Month`;

SELECT MEASURE(`Active Members`) AS `Active Members` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v9` WHERE `Line Of Business` = 'MEDICARE';

SELECT `Enrollment Status`, MEASURE(`Enrollment Records`) AS `Enrollment Records`, MEASURE(`Active Members`) AS `Active Members` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v9` GROUP BY ALL ORDER BY `Enrollment Records` DESC;

SELECT `Participating Provider`, MEASURE(`Total Paid Amount`) AS `Total Paid Amount`, MEASURE(`Participating Provider Paid Amount`) AS `Participating Provider Paid Amount` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v9` GROUP BY ALL ORDER BY `Total Paid Amount` DESC;

SELECT `Claim Type`, MEASURE(`Average Paid per Claim`) AS `Average Paid per Claim`, MEASURE(`Claims per Member`) AS `Claims per Member`, MEASURE(`Lines per Claim`) AS `Lines per Claim` FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v9` GROUP BY ALL ORDER BY `Average Paid per Claim` DESC;
