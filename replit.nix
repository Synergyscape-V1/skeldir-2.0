{ pkgs }: {
  deps = [
    pkgs.nodejs-20_x
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.python311Packages.numpy
    pkgs.python311Packages.pymc
    pkgs.python311Packages.arviz
    pkgs.postgresql_15
    pkgs.bash
    pkgs.git
  ];
  env = {
    PYTHON_LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
      pkgs.stdenv.cc.cc.lib
      pkgs.zlib
      pkgs.python311
      pkgs.blas
      pkgs.lapack
    ];
    PATH = "${pkgs.nodejs-20_x}/bin:${pkgs.python311}/bin:${pkgs.postgresql_15}/bin:$PATH";
    PGDATA = "$REPL_HOME/pgdata";
    PGSOCKET = "$REPL_HOME/.s.PGSQL";
  };
}
