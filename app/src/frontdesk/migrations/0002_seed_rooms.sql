-- Room inventory from docs/api.md: a garden building and a six-floor main building.

INSERT INTO rooms (number, type, max_adults, max_occupancy) VALUES
    ('G01', 'garden',        2, 2),
    ('G02', 'garden',        2, 2),
    ('G03', 'garden',        3, 3),
    ('G04', 'garden',        3, 3),
    ('101', 'economy',       3, 3),
    ('102', 'economy',       3, 3),
    ('103', 'economy',       3, 3),
    ('201', 'standard',      3, 3),
    ('202', 'standard',      3, 3),
    ('203', 'standard',      3, 3),
    ('204', 'standard',      3, 3),
    ('301', 'side_sea_view', 3, 3),
    ('302', 'side_sea_view', 3, 3),
    ('303', 'side_sea_view', 3, 3),
    ('401', 'sea_view',      3, 3),
    ('402', 'sea_view',      3, 3),
    ('403', 'family',        3, 5),
    ('404', 'family',        3, 5),
    ('501', 'family',        3, 5),
    ('502', 'family',        3, 5),
    ('505', 'king_suite',    6, 8),
    ('605', 'king_suite',    6, 8)
ON CONFLICT (number) DO NOTHING;
