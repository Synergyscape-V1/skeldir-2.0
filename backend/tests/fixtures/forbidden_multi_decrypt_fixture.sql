SELECT
  COALESCE(
    pgp_sym_decrypt(encrypted_access_token, 'key_a'),
    pgp_sym_decrypt(encrypted_access_token, 'key_b')
  )
FROM platform_credentials;
