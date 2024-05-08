% Regression test based on demospecret1.m demo

%%  Initialization
%  options for BEM simulation
op = bemoptions( 'sim', 'ret', 'interp', 'curv' );

%  table of dielectric functions
epstab = { epsconst( 1 ), epstable( 'gold.dat' ) };
%  diameter of sphere
diameter = 150;
%  initialize sphere
p = comparticle( epstab, { trisphere( 144, diameter ) }, [ 2, 1 ], 1, op );

%%  BEM simulation
%  set up BEM solver
bem = bemsolver( p, op );

%  plane wave excitation
exc = planewave( [ 1, 0, 0; 0, 1, 0 ], [ 0, 0, 1; 0, 0, 1 ], op );
%  light wavelength in vacuum
enei = linspace( 400, 900, 40 );
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
toc
%  close waitbar
multiWaitbar( 'CloseAll' );

%% Calculate error metrics and plot comparison
sca_original = importdata('test_small_sca.mat');
disp('Max relative error:')
disp(max(abs(sca - sca_original) ./ abs(sca_original), [], 'all'));
disp('Normalized absolute error:')
disp(sum(abs(sca - sca_original), 'all') / sum(abs(sca_original), 'all'))

plot(enei, mean(sca, 2), 'r');
hold on
plot(enei, mean(sca_original, 2), 'b');
