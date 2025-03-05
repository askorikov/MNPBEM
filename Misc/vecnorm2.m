function n = vecnorm2( v, key )
%  vecnorm2 - 2-norm of a vector array.
%
%  Usage :
%    n = vecnorm2( v )
%    n = vecnorm2( v, 'max' )
%  Input
%    v      :  vector array of size (:,3,siz)
%  Output
%    n      :  norm array of size (:,siz) 
%                or maximum of N if 'max' set

n = squeeze( sqrt( dot( abs( v ), abs( v ), 2 ) ) );

%  maximum of N for 'max' keyword
if exist( 'key', 'var' ) && strcmp( key, 'max' ),  n = max( n( : ) );  end
