from users.permissions import IsAdminOrGov

# Postes police : réservés aux comptes gouvernement (GOV) et admin.
IsPoliceUser = IsAdminOrGov
