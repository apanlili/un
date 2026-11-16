# Concept patterns used to count, for each SDG Index indicator, the other ISPAR indices with a KPI on the same measure
# (matched on KPI names in KPI Reference.xlsx; reviewed by hand on 17 October 2026).
CONCEPTS = {
 '1366': r'undernourish', '1367': r'stunting', '1368': r'wasting', '1370': r'human trophic',
 '1373': r'hazardous pesticide', '1378': r'\bhiv\b', '1383': r'adolescent (fertility|birth)', '1384': r'(skilled (health|birth)|births? attended)',
 '1387': r'(subjective well|life satisfaction|cantril)', '1388': r'pre-?primary', '1389': r'net (primary )?enrol+ment.*primary|primary.*net enrol',
 '1390': r'lower secondary completion|completion of lower secondary', '1391': r'literacy', '1394': r'(female|women).*(labou?r force|participation)',
 '1395': r'(seats|parliament).*(women|female)|(women|female).*parliament', '1397': r'sanitation', '1405': r'adjusted gdp growth',
 '1407': r'(account at a (bank|financial)|account ownership|with an account|\baccount\b.*(financial institution|mobile money))',
 '1408': r'unemployment rate', '1413': r'using the internet', '1415': r'(logistics performance|trade.{0,5}and transport.related infrastructure)',
 '1416': r'(times higher education|university ranking|top 3 universities|qs university)', '1418': r'(research and development|r&d|gerd).*(gdp|expenditure)|expenditure on r&d',
 '1419': r'\bgini\b', '1420': r'palma', '1421': r'slum', '1423': r'(piped water|improved water)', '1431': r'plastic waste',
 '1434': r'embodied in fossil', '1438': r'trawl', '1439': r'discard', '1446': r'homicide', '1447': r'(unsentenced|pre-?trial) detain',
 '1449': r'birth regist', '1451': r'child labou?r', '1452': r'(arms|weapons) export', '1458': r'(official development assistance|international concessional)',
 '1459': r'government revenue', '1460': r'tax haven', '3235': r'dietary diversity', '3236': r'patent', '3237': r'shifted profits',
}

# names that share words with a concept but measure something else (laws, satisfaction, sub-groups, digital literacy ...)
EXCLUDE = r'(digital|e-government|legal|mandate|legislation|prohibition|availability|teacher|vocational|advanced education|satisfaction|requirements|eutroph|no account because|do not have|government-provided|for\b.*internet fo)'

# Where the figure used by SDSN comes from, and the route by which a country's own figure can reach it.
# channel: "national data via custodian" = the country reports (survey, register, administrative data) to the agency;
#          "modelled from national data" = the agency estimates from national inputs (the country improves the inputs);
#          "third-party source" = survey, assessment or estimate by another organisation: no reporting route.
CUSTODIAN = {
 '1366': ('FAO', 'modelled from national data', 'food balance sheets and household consumption surveys'),
 '1367': ('UNICEF / WHO / World Bank (JME)', 'national data via custodian', 'DHS, MICS, national nutrition surveys'),
 '1368': ('UNICEF / WHO / World Bank (JME)', 'national data via custodian', 'DHS, MICS, national nutrition surveys'),
 '1370': ('Bonhommeau et al. / FAO food balance', 'third-party source', 'academic estimate'),
 '1373': ('FAO', 'national data via custodian', 'pesticide trade reported to FAO'),
 '1378': ('UNAIDS', 'modelled from national data', 'national HIV estimates (Spectrum)'),
 '1383': ('UN DESA Population Division / WHO', 'modelled from national data', 'civil registration, censuses, surveys'),
 '1384': ('UNICEF / WHO', 'national data via custodian', 'surveys and health information systems'),
 '1387': ('Gallup World Poll', 'third-party source', 'Gallup survey'),
 '1388': ('UNESCO Institute for Statistics', 'national data via custodian', 'annual education survey (ministry of education)'),
 '1389': ('UNESCO Institute for Statistics', 'national data via custodian', 'annual education survey (ministry of education)'),
 '1390': ('UNESCO Institute for Statistics', 'national data via custodian', 'annual education survey and household surveys'),
 '1391': ('UNESCO Institute for Statistics', 'national data via custodian', 'census and household surveys'),
 '1394': ('ILO', 'modelled from national data', 'labour force surveys (ILO modelled estimates)'),
 '1395': ('IPU', 'national data via custodian', 'national parliaments'),
 '1397': ('WHO / UNICEF (JMP)', 'national data via custodian', 'censuses, household surveys, administrative data'),
 '1405': ('World Bank / SDSN', 'modelled from national data', 'national accounts'),
 '1407': ('World Bank Global Findex (Gallup)', 'third-party source', 'Findex survey'),
 '1408': ('ILO', 'modelled from national data', 'labour force surveys'),
 '1413': ('ITU', 'national data via custodian', 'household ICT surveys, regulator data'),
 '1415': ('World Bank LPI', 'third-party source', 'survey of logistics professionals'),
 '1416': ('Times Higher Education', 'third-party source', 'university ranking'),
 '1418': ('UNESCO Institute for Statistics', 'national data via custodian', 'R&D survey'),
 '1419': ('World Bank Poverty and Inequality Platform', 'national data via custodian', 'household income or consumption surveys'),
 '1420': ('OECD / UNDP, from World Bank PIP', 'national data via custodian', 'household income or consumption surveys'),
 '1421': ('UN-Habitat', 'national data via custodian', 'censuses and household surveys'),
 '1423': ('WHO / UNICEF (JMP)', 'national data via custodian', 'censuses, household surveys, administrative data'),
 '1431': ('UN Comtrade', 'national data via custodian', 'customs trade data'),
 '1434': ('UN Comtrade / SDSN', 'national data via custodian', 'customs trade data'),
 '1438': ('Sea Around Us', 'third-party source', 'reconstructed catch estimates'),
 '1439': ('Sea Around Us', 'third-party source', 'reconstructed catch estimates'),
 '1446': ('UNODC', 'national data via custodian', 'police and health statistics (CTS questionnaire)'),
 '1447': ('UNODC', 'national data via custodian', 'prison statistics (CTS questionnaire)'),
 '1449': ('UNICEF', 'national data via custodian', 'civil registration, DHS, MICS'),
 '1451': ('UNICEF / ILO', 'national data via custodian', 'MICS, DHS, child labour surveys'),
 '1452': ('SIPRI', 'third-party source', 'arms transfers database'),
 '1458': ('OECD DAC', 'national data via custodian', 'donor reporting (not applicable to most Arab countries)'),
 '1459': ('IMF', 'national data via custodian', 'government finance statistics'),
 '1460': ('Tax Justice Network', 'third-party source', 'assessment of laws and practices'),
 '3235': ('UNICEF / WHO', 'national data via custodian', 'DHS, MICS, nutrition surveys'),
 '3236': ('WIPO / OECD', 'national data via custodian', 'national patent office statistics'),
 '3237': ('Atlas of the Offshore World (Zucman et al.)', 'third-party source', 'academic estimate'),
}
