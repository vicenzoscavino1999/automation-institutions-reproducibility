# Coverage by chapter and appendix

Manuscript: v22 (`7c568608c9096efb9ccbc40416d171bd631d796daa06e38607eacb6988623d6e`).

This register separates own proofs, arguments inside statements, adjacent derivations and support still pending location. A locator is not an independent proof audit. The package does not simulate the complete HANK-New Keynesian parent model.

The distributed structural check does not require the manuscript. A manuscript-backed check additionally validates the identified v22 hash, labels and source ranges.

## Unit-level coverage

| Unit | Title | Coverage classification | Formal results |
|---|---|---|---:|
| chapter_01 | The Economic Problem: Automation, Access, and Economic Freedom | conceptual_explanation | 0 |
| chapter_02 | What We Know, What We Assume, and Why a Modular Approach Is Necessary | conceptual_explanation | 0 |
| chapter_03 | The HANK-New Keynesian Core of the Transition | conceptual_explanation, unimplemented_module | 0 |
| chapter_04 | Task Frontiers, Displacement, Complementarity, and New Work | analytical_support_located, unimplemented_module, support_pending | 7 |
| chapter_05 | Adoption, Diffusion, and Organizational Capital | analytical_support_located, unimplemented_module, support_pending | 10 |
| chapter_06 | Labor Reallocation, Human Bottlenecks, and the Systemic Extensive-Automation Limit | analytical_support_located, unimplemented_module, support_pending | 10 |
| chapter_07 | Money, Aggregate Demand, and Stability during Automation | analytical_support_located, unimplemented_module | 6 |
| chapter_08 | Concentration, Competition, and AI Rents | analytical_support_located, unimplemented_module, support_pending | 4 |
| chapter_09 | Broad Capital Ownership and Citizen Funds | analytical_support_located, unimplemented_module, support_pending | 3 |
| chapter_10 | Fiscal Capture and Incidence of Technological Gains | analytical_support_located, unimplemented_module, support_pending | 4 |
| chapter_11 | State Capacity, Corruption, and Regulatory Capture | analytical_support_located, unimplemented_module, support_pending | 7 |
| chapter_12 | Institutions That Produce Opportunities | analytical_support_located, unimplemented_module | 7 |
| chapter_13 | International Transmission of the Automation Transition | analytical_support_located, unimplemented_module | 8 |
| chapter_14 | Time Allocation, Effective Freedom, and Life after Work | analytical_support_located, unimplemented_module, support_pending | 4 |
| chapter_15 | Integrated Welfare, Scenario Comparison, and the Conditions for Economic Freedom | analytical_support_located, unimplemented_module, support_pending | 6 |
| chapter_16 | From Automation to Effective Freedom: Reachability, Transition Gates, and Institutional Capacity | analytical_support_located, finite_computational_check | 3 |
| appendix_A | A Worked Reduced Economy of Automation, Direct Demand, and Opportunity | reproduced_numeric_result, finite_computational_check | 0 |
| appendix_B | Technical Appendix to Chapter 3 | analytical_support_located | 0 |
| appendix_C | Technical Appendix to Chapter 4 | analytical_support_located | 0 |
| appendix_D | Technical Appendix to Chapter 5 | analytical_support_located | 0 |
| appendix_E | Technical Appendix to Chapter 6 | analytical_support_located, support_pending | 1 |
| appendix_F | Technical Appendix to Chapter 7 | analytical_support_located | 0 |
| appendix_G | Technical Appendix to Chapter 8 | analytical_support_located | 0 |
| appendix_H | Technical Appendix to Chapter 9 | analytical_support_located | 0 |
| appendix_I | Technical Appendix to Chapter 10 | analytical_support_located | 0 |
| appendix_J | Technical Appendix to Chapter 11 | analytical_support_located | 0 |
| appendix_K | Technical Appendix to Chapter 12 | analytical_support_located | 0 |
| appendix_L | Technical Appendix to Chapter 13 | analytical_support_located | 1 |
| appendix_M | Technical Appendix to Chapter 14 | analytical_support_located | 0 |
| appendix_N | Technical Appendix to Chapter 15 | analytical_support_located | 1 |
| reference_tables | Reference tables: notation and interfaces | conceptual_explanation | 0 |

## Computational links

| Unit | Object | Files | Scope |
|---|---|---|---|
| chapter_07 | direct-demand incidence | RUN_DIR/results/scenarios.csv | reduced first-round slice; no NK equilibrium-output simulation |
| chapter_10 | gross capture and net public resources | RUN_DIR/results/scenarios.csv, RUN_DIR/results/cash_ledger.csv | synthetic fiscal instrument only |
| chapter_11 | capacity conversion parameter | RUN_DIR/results/scenarios.csv, RUN_DIR/results/sensitivity.csv | reduced capacity law; no estimated state process |
| chapter_12 | future service and opportunity gate | RUN_DIR/results/scenarios.csv, RUN_DIR/results/analytical_conditions.csv | single synthetic opportunity service |
| chapter_16 | two gates and finite feasibility checks | RUN_DIR/independent/oracle_results.json, RUN_DIR/results/conditional_gate_regions.csv | three finite complements; no viability kernel |
| appendix_A | worked reduced economy A-E | RUN_DIR/results/scenarios.csv, RUN_DIR/results/constructive_case.csv, RUN_DIR/results/optimization_summary.csv | reproduced numerical result |

## Formal-result locators

| Unit | Environment | Label | Statement | Hypotheses | Analytical support | Computational status |
|---|---|---|---:|---|---|---|
| chapter_04 | characterization | `prop:task_assignment_ch4` | 2795-2798 | formal statement | own_proof at lines 14079-14082 | not_implemented_for_this_result |
| chapter_04 | proposition | `prop:direct_displacement_ch4` | 2872-2875 | formal statement | own_proof at lines 14083-14095 | not_implemented_for_this_result |
| chapter_04 | characterization | `prop:augmentation_ch4` | 2889-2892 | formal statement | own_proof at lines 14096-14099 | not_implemented_for_this_result |
| chapter_04 | proposition | `prop:scale_ambiguity_ch4` | 2918-2921 | formal statement | adjacent_derivation at lines 2908-2920 | not_implemented_for_this_result |
| chapter_04 | diagnostic | `prop:resource_rebound_ch4` | 2946-2955 | formal statement | support_pending | not_implemented_for_this_result |
| chapter_04 | characterization | `prop:reinstatement_ch4` | 3004-3007 | formal statement | own_proof at lines 14100-14103 | not_implemented_for_this_result |
| chapter_04 | sufficientcondition | `prop:human_bottleneck_ch4` | 3312-3315 | formal statement | own_proof at lines 14104-14116 | not_implemented_for_this_result |
| chapter_05 | proposition | `prop:adoption_threshold_ch5` | 3708-3711 | formal statement | own_proof at lines 14180-14191 | not_implemented_for_this_result |
| chapter_05 | proposition | `prop:organization_finance_ch5` | 3744-3747 | formal statement | own_proof at lines 14192-14205 | not_implemented_for_this_result |
| chapter_05 | proposition | `prop:selection_adoption_ch5` | 3789-3800 | formal statement | own_proof at lines 14206-14219 | not_implemented_for_this_result |
| chapter_05 | proposition | `prop:option_wait_ch5` | 3899-3902 | formal statement | own_proof at lines 14220-14231 | not_implemented_for_this_result |
| chapter_05 | proposition | `prop:diffusion_contraction_ch5` | 3955-3966 | formal statement | own_proof at lines 14232-14244 | not_implemented_for_this_result |
| chapter_05 | proposition | `prop:multiple_adoption_ch5` | 4006-4036 | formal statement | own_proof at lines 14245-14331 | not_implemented_for_this_result |
| chapter_05 | lemma | `lem:global_scalar_ch5` | 4038-4041 | formal statement | own_proof at lines 14332-14341 | not_implemented_for_this_result |
| chapter_05 | corollary | `cor:fold_policy_ch5` | 4043-4046 | formal statement | own_proof at lines 14342-14345 | not_implemented_for_this_result |
| chapter_05 | proposition | `prop:learning_wedge_ch5` | 4064-4076 | formal statement | own_proof at lines 14346-14349 | not_implemented_for_this_result |
| chapter_05 | diagnostic | `prop:size_not_adoption_order_ch5` | 4168-4171 | formal statement | support_pending | not_implemented_for_this_result |
| chapter_06 | proposition | `prop:exposure_non_equivalence_ch6` | 4918-4921 | formal statement | own_proof at lines 14480-14487 | not_implemented_for_this_result |
| chapter_06 | proposition | `prop:training_threshold_ch6` | 4991-4994 | formal statement | support_pending | not_implemented_for_this_result |
| chapter_06 | proposition | `prop:liquidity_training_ch6` | 4998-5009 | formal statement | own_proof at lines 14488-14491 | not_implemented_for_this_result |
| chapter_06 | proposition | `prop:mobility_logit_ch6` | 5013-5023 | formal statement | own_proof at lines 14492-14500 | not_implemented_for_this_result |
| chapter_06 | proposition | `prop:dynamic_complementarity_ch6` | 5046-5049 | formal statement | own_proof at lines 14501-14511 | not_implemented_for_this_result |
| chapter_06 | sufficientcondition | `prop:system_bottleneck_ch6` | 5329-5338 | formal statement | own_proof at lines 14512-14515 | not_implemented_for_this_result |
| chapter_06 | proposition | `prop:ces_regimes_ch6` | 5370-5383 | formal statement | own_proof at lines 14516-14528 | not_implemented_for_this_result |
| chapter_06 | proposition | `prop:growth_regimes_ch6` | 5402-5411 | formal statement | own_proof at lines 14529-14537 | not_implemented_for_this_result |
| chapter_06 | characterization | `prop:directional_innovation_ch6` | 5509-5512 | formal statement | support_pending | not_implemented_for_this_result |
| chapter_06 | proposition | `prop:opportunity_value_ch6` | 5551-5561 | formal statement | argument_in_statement at lines 5551-5560 | not_implemented_for_this_result |
| chapter_07 | accountingresult | `prop:mpc_exposure_decomposition_ch7` | 5839-5857 | formal statement | own_proof at lines 14571-14590 | not_implemented_for_this_result |
| chapter_07 | proposition | `prop:aggregate_equivalence_ch7` | 5861-5864 | formal statement | argument_in_statement at lines 5861-5863 | not_implemented_for_this_result |
| chapter_07 | characterization | `prop:sharp_joint_incidence_bounds_ch7` | 5868-5884 | formal statement | own_proof at lines 5886-5888 | not_implemented_for_this_result |
| chapter_07 | proposition | `prop:fiscal_capture_threshold_ch7` | 6048-6069 | formal statement | own_proof at lines 14631-14648 | not_implemented_for_this_result |
| chapter_07 | proposition | `prop:nominal_propagation_ch7` | 6116-6135 | formal statement | own_proof at lines 14662-14684 | not_implemented_for_this_result |
| chapter_07 | diagnostic | `prop:conditional_realized_output_threshold_ch7` | 6331-6367 | formal statement | own_proof at lines 14685-14728 | not_implemented_for_this_result |
| chapter_08 | proposition | `prop:adoption_concentration_ch8` | 6643-6665 | formal statement | own_proof at lines 14732-14762 | not_implemented_for_this_result |
| chapter_08 | accountingresult | `prop:free_entry_value_gap_ch8` | 6832-6835 | formal statement | support_pending | not_implemented_for_this_result |
| chapter_08 | proposition | `prop:data_feedback_stability_ch8` | 7035-7044 | formal statement | own_proof at lines 14763-14784 | not_implemented_for_this_result |
| chapter_08 | corollary | `cor:data_sharing_local_ch8` | 7058-7074 | formal statement | own_proof at lines 14785-14794 | not_implemented_for_this_result |
| chapter_09 | accountingresult | `prop:no_free_asset_ch9` | 7730-7742 | formal statement | support_pending | not_implemented_for_this_result |
| chapter_09 | proposition | `prop:portfolio_offset_ch9` | 7894-7897 | formal statement | own_proof at lines 7899-7901 | not_implemented_for_this_result |
| chapter_09 | proposition | `prop:fund_payout_incidence_ch9` | 8029-8059 | formal statement | argument_in_statement at lines 8029-8058 | not_implemented_for_this_result |
| chapter_10 | accountingresult | `prop:local_revenue_ch10` | 8500-8503 | formal statement | adjacent_derivation at lines 8478-8505 | not_implemented_for_this_result |
| chapter_10 | proposition | `prop:cash_flow_neutrality_ch10` | 8695-8698 | formal statement | support_pending | not_implemented_for_this_result |
| chapter_10 | diagnostic | `prop:technology_sign_ch10` | 8836-8839 | formal statement | own_proof at lines 8841-8843 | not_implemented_for_this_result |
| chapter_10 | proposition | `prop:tax_ownership_boundary_ch10` | 9071-9074 | formal statement | own_proof at lines 9076-9078 | not_implemented_for_this_result |
| chapter_11 | proposition | `prop:audit_allocation_ch11` | 9398-9408 | formal statement | own_proof at lines 9410-9412 | not_implemented_for_this_result |
| chapter_11 | proposition | `prop:official_incentive_ch11` | 9435-9446 | formal statement | own_proof at lines 9448-9450 | not_implemented_for_this_result |
| chapter_11 | accountingresult | `prop:integrity_ledger_ch11` | 9510-9513 | formal statement | own_proof at lines 9515-9517 | not_implemented_for_this_result |
| chapter_11 | proposition | `prop:rules_discretion_ch11` | 9590-9593 | formal statement | own_proof at lines 9595-9597 | not_implemented_for_this_result |
| chapter_11 | proposition | `prop:concentration_capture_ch11` | 9720-9723 | formal statement | own_proof at lines 9725-9727 | not_implemented_for_this_result |
| chapter_11 | diagnostic | `prop:decisive_veto_ch11` | 9819-9831 | formal statement | support_pending | not_implemented_for_this_result |
| chapter_11 | proposition | `prop:local_global_capacity_ch11` | 9863-9866 | formal statement | own_proof at lines 9868-9870 | not_implemented_for_this_result |
| chapter_12 | diagnostic | `prop:input_opportunity_nonequivalence_ch12` | 10274-10277 | formal statement | own_proof at lines 10279-10281 | not_implemented_for_this_result |
| chapter_12 | proposition | `prop:installed_capital_ch12` | 10306-10309 | formal statement | own_proof at lines 10311-10313 | not_implemented_for_this_result |
| chapter_12 | proposition | `prop:universal_access_ch12` | 10400-10403 | formal statement | own_proof at lines 10405-10407 | not_implemented_for_this_result |
| chapter_12 | proposition | `prop:conditional_congestion_ch12` | 10467-10470 | formal statement | argument_in_statement at lines 10467-10469 | not_implemented_for_this_result |
| chapter_12 | interfacelemma | `lem:nonlinear_handoff_ch12` | 10528-10537 | formal statement | own_proof at lines 10539-10546 | not_implemented_for_this_result |
| chapter_12 | proposition | `prop:targeting_ambiguity_ch12` | 10738-10741 | formal statement | own_proof at lines 10743-10745 | not_implemented_for_this_result |
| chapter_12 | proposition | `prop:participant_aggregate_ch12` | 10773-10776 | formal statement | own_proof at lines 10778-10780 | not_implemented_for_this_result |
| chapter_13 | proposition | `prop:household_external_inflation_ch13` | 11114-11124 | formal statement | own_proof at lines 11126-11128 | not_implemented_for_this_result |
| chapter_13 | proposition | `prop:digital_embodied_trade_ch13` | 11225-11228 | formal statement | own_proof at lines 11230-11232 | not_implemented_for_this_result |
| chapter_13 | proposition | `prop:frontier_deployment_ch13` | 11271-11274 | formal statement | own_proof at lines 11276-11278 | not_implemented_for_this_result |
| chapter_13 | proposition | `prop:foreign_automation_ambiguity_ch13` | 11314-11317 | formal statement | own_proof at lines 11319-11321 | not_implemented_for_this_result |
| chapter_13 | proposition | `prop:representative_external_exposure_ch13` | 11376-11379 | formal statement | own_proof at lines 11381-11383 | not_implemented_for_this_result |
| chapter_13 | accountingresult | `prop:gdp_resident_income_ch13` | 11432-11435 | formal statement | own_proof at lines 11437-11439 | not_implemented_for_this_result |
| chapter_13 | proposition | `prop:depreciation_ambiguity_ch13` | 11523-11526 | formal statement | own_proof at lines 11528-11530 | not_implemented_for_this_result |
| chapter_13 | accountingresult | `prop:use_ownership_tax_ch13` | 11581-11584 | formal statement | own_proof at lines 11586-11588 | not_implemented_for_this_result |
| chapter_14 | accountingresult | `ares:primary_secondary_time_ch14` | 11918-11921 | formal statement | own_proof at lines 11923-11925 | not_implemented_for_this_result |
| chapter_14 | proposition | `prop:material_security_work_ch14` | 12104-12107 | formal statement | own_proof at lines 12109-12111 | not_implemented_for_this_result |
| chapter_14 | proposition | `prop:resources_not_sufficient_ch14` | 12372-12375 | formal statement | own_proof at lines 12377-12379 | not_implemented_for_this_result |
| chapter_14 | proposition | `prop:conditional_existence_ch14` | 12430-12433 | formal statement | support_pending | not_implemented_for_this_result |
| chapter_15 | accountingresult | `res:claims_consolidation_ch15` | 12587-12590 | formal statement | support_pending | not_implemented_for_this_result |
| chapter_15 | proposition | `prop:distributional_noninvariance_ch15` | 12675-12678 | formal statement | support_pending | not_implemented_for_this_result |
| chapter_15 | diagnostic | `prop:local_global_firewall_ch15` | 12724-12727 | formal statement | support_pending | not_implemented_for_this_result |
| chapter_15 | sufficientcondition | `prop:two_layer_dominance_ch15` | 12780-12783 | formal statement | argument_in_statement at lines 12780-12783 | not_implemented_for_this_result |
| chapter_15 | sufficientcondition | `prop:institutional_conversion_ch15` | 12900-12903 | formal statement | own_proof at lines 12905-12907 | not_implemented_for_this_result |
| chapter_15 | sufficientcondition | `prop:inclusive_endpoint_ch15` | 12933-12936 | formal statement | own_proof at lines 12938-12940 | not_implemented_for_this_result |
| chapter_16 | diagnostic | `prop:collection_execution_no_go_ch16` | 13256-13264 | formal statement | own_proof at lines 13266-13273 | finite_computational_check |
| chapter_16 | proposition | `prop:two_gate_separation_ch16` | 13292-13322 | formal statement | own_proof at lines 13324-13334 | finite_computational_check |
| chapter_16 | sufficientcondition | `prop:primitive_capacity_trap_ch16` | 13401-13417 | formal statement | own_proof at lines 13419-13427 | finite_computational_check |
| appendix_E | proposition | `prop:mismatch_amplification_ch6` | 14451-14460 | formal statement | support_pending | not_implemented_for_this_result |
| appendix_L | accountingresult | `prop:cross_border_ledger_conservation_ch13` | 15515-15518 | formal statement | own_proof at lines 15520-15522 | not_implemented_for_this_result |
| appendix_N | invarianceresult | `prop:refinement_invariance_ch15` | 15711-15722 | formal statement | own_proof at lines 15724-15726 | not_implemented_for_this_result |

## Interpretation

The registry says where a result is stated, where its declared analytical support is located when identified, and whether a finite calculation accompanies it. A later citation is not a proof. `support_pending` records that no qualifying support locator was established by this finite audit. The register does not certify every proof, estimate empirical parameters, or establish that the parent architecture is jointly computable.
