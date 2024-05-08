% Performance test based on demospecret1.m with a larger mesh

%%  Initialization
%  options for BEM simulation
op = bemoptions( 'sim', 'ret', 'interp', 'flat' );

%  table of dielectric functions
epstab = { epsconst( 1 ), epstable( 'gold.dat' ) };
%  nanorod parameters
diameter = 30;
height = 90;
n_elements = [30, 30, 30];  % [nphi, ntheta, nz]
%  initialize sphere
p = comparticle( epstab, { trirod(diameter, height, n_elements, 'triangles') }, [ 2, 1 ], 1, op );

%%  BEM simulation
%  set up BEM solver
bem = bemsolver( p, op );

%  plane wave excitation
exc = planewave( [ 1, 0, 0; 0, 1, 0 ], [ 0, 0, 1; 0, 0, 1 ], op );
%  light wavelength in vacuum
enei = linspace( 400, 900, 3 );
%  allocate scattering and extinction cross sections
sca = zeros( length( enei ), 2 );
ext = zeros( length( enei ), 2 );

multiWaitbar( 'BEM solver', 0, 'Color', 'g', 'CanCancel', 'on' );
%  loop over wavelengths
tic
for ien = 1 : length( enei )
  %  surface charge
  sig = bem \ exc( p, enei( ien ) );
  %  scattering and extinction cross sections
  sca( ien, : ) = exc.sca( sig );
  ext( ien, : ) = exc.ext( sig );
  
  multiWaitbar( 'BEM solver', ien / numel( enei ) );
end
%  close waitbar
multiWaitbar( 'CloseAll' );
fprintf('Time per iteration: %.1f s\n', toc / length(enei));
