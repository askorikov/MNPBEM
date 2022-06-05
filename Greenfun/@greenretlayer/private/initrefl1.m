function obj = initrefl1( obj, enei )
%  INITREFL1 - Initialize reflected part of Green function.
%    We compute G and the surface derivative F.
%
%  Usage for obj = greenretlayer :
%    obj = initrefl( obj, enei )
%  Input
%    enei    :  wavelength of light in vacuum

%  tabulated Green functions
obj.tab = eval( obj.tab, enei );  tab = obj.tab;

%  particles or point positions
[ pos1, pos2 ] = deal( obj.p1.pos, obj.p2.pos );
%  difference vectors
x = bsxfun( @minus, pos1( :, 1 ), pos2( :, 1 ) .' );
y = bsxfun( @minus, pos1( :, 2 ), pos2( :, 2 ) .' );
%  radii
r = sqrt( x .^ 2 + y .^ 2 );
%  positions in z-direction
z1 = repmat( pos1( :, 3 ), 1, size( r, 2 ) );
z2 = repmat( pos2( :, 3 ), 1, size( r, 1 ) ) .';

%  normal vector
nvec = obj.p1.nvec;
%  inner product
in = ( bsxfun( @times, x, nvec( :, 1 ) ) +  ...
       bsxfun( @times, y, nvec( :, 2 ) ) ) ./ max( r, 1e-10 );                 
%  perform interpolation
[ G, Fr, Fz ] = interp( tab, r, z1, z2 );

%  get field names
names = fieldnames( G );
%  multiply with area and compose surface derivative of Green function
for i = 1 : length( names )
  G.( names{ i } ) = bsxfun( @times, G.( names{ i } ), obj.p2.area .' );
  %  surface derivative of Green function
  F.( names{ i } ) =  bsxfun( @times,          ... 
                    Fr.( names{ i } ) .* in +  ...
    bsxfun( @times, Fz.( names{ i } ), nvec( :, 3 ) ), obj.p2.area .' );
end

%%  refine diagonal elements 
if ~isempty( obj.id )
  %  particle and index to diagonal elements
  [ p, id2 ] = deal( obj.p1, obj.id );
  %  row index
  [ id, ~ ] = ind2sub( p.n * [ 1, 1 ], id2 );
  
  %  integration points and weights for polar integration
  [ pos1, weight, row ] = quadpol( p, id );
  %  centroids (expand to size of integration points)
  pos2 = p.pos( id( row ), : );
  
  %  difference vectors
  x = pos1( :, 1 ) - pos2( :, 1 );
  y = pos1( :, 2 ) - pos2( :, 2 );
  %  radial distance between points
  r = sqrt( x .^ 2 + y .^ 2 );
  %  positions in z-direction
  z1 = pos1( :, 3 );
  z2 = pos2( :, 3 );  
  
  %  normal vector
  nvec = obj.p1.nvec( id( row ), : );
  %  inner product
  in = ( bsxfun( @times, x, nvec( :, 1 ) ) +  ...
         bsxfun( @times, y, nvec( :, 2 ) ) ) ./ max( r, 1e-10 );   
 
  %  perform interpolation
  [ g, fr, fz, r, z ] = interp( obj.tab, r, z1, z2 );
  %  distance
  rr = sqrt( r .^ 2 + z .^ 2 );
  
  % %  refine diagonal elements (w/o explicit consideration of divergent term)
  % for i = 1 : length( names )
  %   G.( names{ i } )( ind2 ) = accumarray( row, weight .* g.(  names{ i } ) );
  %   F.( names{ i } )( ind2 ) = accumarray( row, weight .*  ...
  %     ( fr.( names{ i } ) .* in + bsxfun( @times, fz.( names{ i } ), nvec( :, 3 ) ) ) );
  % end  
  
  %  index to positions located inside layer
  [ ~, lin ] = indlayer( obj.layer, p.pos( id, 3 ) );
  %  expand to size of integration points
  linrow = lin( row );
  %  matrix index
  lin2 = sub2ind( p.n * [ 1, 1 ], id( lin ), id( lin ) );
  
  %  layer index and layer position
  [ ~, ind ] = mindist( obj.layer, p.pos( id( lin ), 3 ) );
  z0 = obj.layer.z( ind );
  %  direction from layer to particle boundary
  dir = sign( p.pos( id( lin ), 3 ) - obj.layer.z( ind ) );
  %  element with r -> 0, z -> 0
  if any( lin )
    [ ~, ~, f0, r0, z0 ] =  ...
      interp( obj.tab, 0 * z0, z0 + 1e-10 * dir, z0 + 1e-10 * dir );
  end
  
  %  f0 is given at particle centroids of boundary elements in the layer, 
  %    IROW expands the centroid index to the integration points
  [ irow, ~, n ] = unique( row( any( bsxfun( @eq, row, find( lin )' ), 2 ) ) );
  %  replace elements ( i1, i1, i2, ... ) with ( 1, 1, 2, ... )
  irow = subsref( 1 : numel( irow ), substruct( '()', { n } ) );

  %  refine diagonal elements
  for i = 1 : length( names )
    %  integrate Green function
    G.( names{ i } )( id2 ) = accumarray( row, weight .* g.( names{ i } ) );

    %  surface derivative of Green function
    fzi = fz.( names{ i } );        
    %  element with r -> 0, z -> 0
    %    Waxenegger et al., Comp. Phys. Commun. 193, 138 (2015), Eq. (17).
    if any( lin )
      f = f0.( names{ i } ) .* ( r0 .^ 2 + z0 .^ 2 ) .^ 1.5 ./ z0;    
      %  subtract divergent part for boundary elements in layer
      fzi( linrow ) = fzi( linrow ) - f( irow ) .* z( linrow ) ./ rr( linrow ) .^ 3;
      %  reshape z-derivative of Green function
      fzi = reshape( fzi, size( fz.( names{ i } ) ) );
    else
      f = 0;
    end
    
    %  integrate surface derivative of Green function w/o divergent term
    F.( names{ i } )( id2 ) = accumarray( row, weight .*  ...
      ( fr.( names{ i } ) .* in + bsxfun( @times, fzi, nvec( :, 3 ) ) ) );
    %  add divergent term
    F.( names{ i } )( lin2 ) =  ...
    F.( names{ i } )( lin2 ) + 2 * pi * f .* obj.p1.nvec( id( lin ), 3 );
  end
end

%%  refine off-diagonal elements
if ~isempty( obj.ind ) && ~isempty( obj.ir )
  %  refinement with Green function interpolation in boundary elements
  [ g, fr, fz ] = interp( obj.tab, obj.ir, obj.iz( :, 1 ), obj.iz( :, 2 ) );
  %  refine elements
  for i = 1 : length( names )
    G.( names{ i } )( obj.ind ) = obj.ig  * g.(  names{ i } );
    F.( names{ i } )( obj.ind ) = obj.ifr * fr.( names{ i } ) + ...
                                  obj.ifz * fz.( names{ i } );
  end
  
elseif ~isempty( obj.ind )
  %  size of Green function
  siz = size( G.p );
  %  full integration over boundary elememts
  ind = reshape( accumarray( obj.ind, 1, [ prod( siz ), 1 ] ), siz );
  %  find elements with refinement
  [ ~, column ] = find( ind );
  %  loop over elements with refinememt
  for col = unique( column ) .'
    %  find corresponding rows
    row = find( ind( :, col ) );
    %  positions
    pos1 = obj.p1.pos( row, : );
    [ pos2, weight ] = quad( obj.p2, col );
    
    %  difference vectors
    x = bsxfun( @minus, pos1( :, 1 ), pos2( :, 1 ) .' );
    y = bsxfun( @minus, pos1( :, 2 ), pos2( :, 2 ) .' );
    %  radii
    r = sqrt( x .^ 2 + y .^ 2 );
    %  positions in z-direction
    z1 = repmat( pos1( :, 3 ), 1, size( r, 2 ) );
    z2 = repmat( pos2( :, 3 ), 1, size( r, 1 ) ) .';      

    %  normal vector
    nvec = obj.p1.nvec( row, : );
    %  inner product
    in = ( bsxfun( @times, x, nvec( :, 1 ) ) +  ...
           bsxfun( @times, y, nvec( :, 2 ) ) ) ./ max( r, 1e-10 );                 
    %  perform interpolation
    [ g, fr, fz ] = interp( obj.tab, r, z1, z2 );
    
    %  refine diagonal elements
    for i = 1 : length( names )
      G.( names{ i } )( row, col ) = g.( names{ i } ) * weight( : );
      F.( names{ i } )( row, col ) =               ...
                      ( fr.( names{ i } ) .* in +  ...
        bsxfun( @times, fz.( names{ i } ), nvec( :, 3 ) ) ) * weight( : );
    end 
  end
  
end

%%  save reflected part of Green function
[ obj.G, obj.F ] = deal( G, F );
