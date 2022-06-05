function [ sig, obj ] = solve( obj, exc, ~ )
%  SOLVE - Compute surface charges and currents for given excitation.
%
%  Usage for obj = bemret :
%    [ sig, obj ] = solve( obj, exc )
%  Input
%    exc    :  compstruct with fields for external excitation
%  Output
%    sig    :  compstruct with fields for surface charges and currents

[ sig, obj ] = mldivide( obj, exc );
