module
public import Init
set_option autoImplicit false
set_option maxRecDepth 100000
set_option maxHeartbeats 1000000000
set_option linter.constructorNameAsVariable false
namespace TropicalRouter.Main

@[expose] public def tropicalMul (w : Nat) (x : Nat) : Nat := (w + x)

@[expose] public def tropicalScore (w : Nat) (x : Nat) (b : Nat) : Nat := ((w + x) + b)

public theorem router_smoke_eval : (tropicalScore (3) (5) (2) = 10) := by
  decide

end TropicalRouter.Main
