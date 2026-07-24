# Vendored fixtures

`orders/model.yaml` and `orders/seed.sql` are copied verbatim from datus-osi
(`fixtures/orders/`) so the integration tests don't couple to a checkout of
that repo. They can drift from upstream; refresh them if the OSI spec or the
fixture changes.
